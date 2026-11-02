"""Causal, one-request-at-a-time RGB scheduler pilot.

This measures a proxy furniture-visibility task, never safety-event recall.
Models receive only the current full RGB image, not annotations or future frames.
Recorded responses retain their measured latency; cache access time is not inference.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"chair", "table", "sofa", "cabinet", "bed", "shelf"}
DEADLINES = (2, 5, 10, 20)


def digest(value: Any) -> str:
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows))


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def validate_manifest(frames: list[dict]) -> None:
    ids, videos, groups = set(), {}, {}
    for frame in frames:
        identifier = frame["frame_id"]
        if identifier in ids:
            raise ValueError(f"duplicate frame_id: {identifier}")
        ids.add(identifier)
        t=float(frame["pts_s"])
        if not math.isfinite(t) or t < 0 or t > float(frame["duration_s"]):
            raise ValueError(f"invalid frame timestamp: {identifier}")
        group=frame.get("site_id") or frame.get("visit_id")
        if not group:
            raise ValueError("Missing acquisition group; cannot establish dev/test separation")
        split=frame["split"]
        if split not in {"dev","test"}:
            raise ValueError("Invalid split")
        if group in groups and groups[group] != split:
            raise ValueError("Acquisition group crosses development and test")
        groups[group]=split
        entry=videos.setdefault(frame["video_id"],{"split":split,"group":group,"times":set()})
        if (entry["split"],entry["group"]) != (split,group) or t in entry["times"]:
            raise ValueError("Video group inconsistency or duplicate PTS")
        entry["times"].add(t)


def hamming(a: str | None, b: str | None) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count() if a and b and len(a) == len(b) else 64


def features(image: Image.Image) -> dict:
    """Exact H5 inspectPixels arithmetic on a <=720 edge RGB observation.

    H5 hash is a 64-bit horizontal difference hash, not a DCT pHash.
    Additional tile vector is automatic image evidence for D only.
    """
    image = image.convert("RGB")
    w, h = image.size
    if max(w, h) > 720:
        scale = 720 / max(w, h)
        image = image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BILINEAR)
    a = np.asarray(image, dtype=np.float64)
    gray = a[:, :, 0] * .299 + a[:, :, 1] * .587 + a[:, :, 2] * .114
    h, w = gray.shape
    step = max(1, min(w, h) // 80)
    ys, xs = np.arange(step, h - step, step), np.arange(step, w - step, step)
    if len(ys) and len(xs):
        y, x = np.meshgrid(ys, xs, indexing="ij")
        center = gray[y, x]
        brightness = float(center.mean())
        sharpness = float(np.abs(4 * center - gray[y, x-step] - gray[y, x+step] - gray[y-step, x] - gray[y+step, x]).mean())
    else:
        brightness = sharpness = 0.0
    bits = "".join("1" if gray[min(h-1, math.floor((yy+.5)/8*h)), min(w-1, math.floor(xx/9*w))] < gray[min(h-1, math.floor((yy+.5)/8*h)), min(w-1, math.floor((xx+1)/9*w))] else "0" for yy in range(8) for xx in range(8))
    small = np.asarray(image.convert("L").resize((128, 96), Image.Resampling.BILINEAR), dtype=np.float32) / 255
    return {"brightness": brightness, "sharpness": sharpness, "hash": f"{int(bits, 2):016x}", "small": small}


def local_change(current: np.ndarray, previous: np.ndarray | None) -> float:
    if previous is None:
        return 0.0
    difference = np.abs(current - previous)
    # 8x8 tiles. Maximum tile change can expose changes hidden by a global hash.
    return float(difference.reshape(8, 12, 8, 16).mean(axis=(1, 3)).max())


@dataclass
class Policy:
    name: str
    kind: str
    interval_s: float = 6
    hash_threshold: int = 6
    resolution: int = 720
    maximum_requests: int = 30
    max_silence_s: float = 12
    result_ttl_s: float = 12
    local_threshold: float = .12
    previous_hash: str | None = None
    submitted_hash: str | None = None
    submitted_small: np.ndarray | None = None
    next_allowed: float = -math.inf
    last_sent: float = -math.inf
    last_result_source: float = -math.inf
    requests: int = 0
    failures: int = 0
    last_usable: bool | None = None
    public_results: list[dict] = field(default_factory=list)

    def decide(self, t: float, f: dict, busy: bool) -> tuple[str, str, dict]:
        if busy:
            return "wait", "inflight", {}
        if self.requests >= self.maximum_requests:
            return "wait", "request_cap", {}
        if t < self.next_allowed:
            return "wait", "cooldown", {}
        if self.kind == "fixed":
            return ("low" if self.resolution == 720 else "high", "fixed_interval", {}) if t-self.last_sent >= self.interval_s else ("wait", "fixed_interval_wait", {})
        motion = hamming(f["hash"], self.previous_hash) / 64 if self.previous_hash else 0
        self.previous_hash = f["hash"]
        extra = {"motion": motion}
        if not 28 <= f["brightness"] <= 232:
            return "wait", "brightness_gate", extra
        if f["sharpness"] < 5 or motion > .48:
            return "wait", "sharpness_or_motion_gate", extra
        duplicate = self.submitted_hash is not None and hamming(f["hash"], self.submitted_hash) < self.hash_threshold
        if self.kind == "candidate":
            change = local_change(f["small"], self.submitted_small)
            silent = self.requests > 0 and t-self.last_sent >= self.max_silence_s
            expired = self.last_usable is not None and t-self.last_result_source >= self.result_ttl_s
            extra.update(local_change=change, result_expired=expired, silence_due=silent)
            if duplicate and change < self.local_threshold and not silent and not expired:
                return "wait", "duplicate", extra
            action = "high" if change >= self.local_threshold or expired or self.last_usable is False else "low"
            reason = "local_change" if change >= self.local_threshold else "expired_result" if expired else "max_silence" if silent else "global_change"
            return action, reason, extra
        if duplicate:
            return "wait", "duplicate", extra
        return "low" if self.resolution == 720 else "high", "global_change", extra

    def sent(self, t: float) -> None:
        self.requests += 1
        self.last_sent = t

    def returned(self, when: float, source_t: float, f: dict, response: dict) -> None:
        self.public_results.append({"available_at_s": when, "source_pts_s": source_t, "response": response})
        valid = response.get("status") == "ok" and isinstance(response.get("result"), dict)
        if self.kind == "fixed":
            return
        if valid:
            usable = response["result"].get("quality_usable") is True
            self.last_usable = usable
            # B intentionally preserves the rejected-frame hash poisoning.
            if self.kind == "original" or usable:
                self.submitted_hash, self.submitted_small = f["hash"], f["small"]
            if not usable:
                if self.kind != "original":
                    self.failures += 1
                    self.next_allowed = when + min(16, 2 * 2 ** self.failures)
                return
            self.last_result_source = source_t
            self.failures = 0
            self.next_allowed = when + self.interval_s
        else:
            self.failures += 1
            self.next_allowed = when + min(16, 2 * 2 ** self.failures)


class HTTPModel:
    def __init__(self, endpoint: str, cache_dir: Path, model_contract: dict, timeout_s: float = 120, max_retries: int = 1, send_image: bool = True, use_cache: bool = True):
        if urllib.parse.urlparse(endpoint).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("This zero-API-cost adapter only permits a local model endpoint")
        self.endpoint, self.cache_dir, self.contract = endpoint, cache_dir, model_contract
        self.timeout_s, self.max_retries, self.send_image, self.use_cache = timeout_s, max_retries, send_image, use_cache
        cache_dir.mkdir(parents=True, exist_ok=True)

    def call(self, image_path: Path, request_id: str) -> dict:
        image_bytes = image_path.read_bytes()
        key = digest({"image_sha256": digest(image_bytes), "model_contract": self.contract, "timeout_s": self.timeout_s, "max_retries": self.max_retries})
        cached = self.cache_dir / f"{key}.json"
        if self.use_cache and cached.exists():
            value = json.loads(cached.read_text())
            value.update(execution_mode="recorded_response", cache_key=key, original_request_id=value["request_id"], request_id=request_id)
            return value
        payload = {"request_id": request_id, "image_path": str(image_path.resolve())}
        if self.send_image:
            payload.update(image_base64=base64.b64encode(image_bytes).decode(), mime_type="image/jpeg")
        body = json.dumps(payload).encode()
        attempts = []
        total_start = time.monotonic()
        response = {}
        for attempt in range(self.max_retries + 1):
            start = time.monotonic()
            status_code, error, retryable = None, None, False
            raw_text = ""
            try:
                request = urllib.request.Request(self.endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=self.timeout_s) as r:
                    status_code = r.status
                    raw_text = r.read().decode()
                    response = json.loads(raw_text)
                if response.get("status") not in {"ok", "invalid", "error"}:
                    raise ValueError("invalid_server_status")
                if response.get("status") == "ok":
                    for field_name in ("model_id", "model_revision", "prompt_sha256", "decoding_version", "server_code_sha256"):
                        expected = self.contract.get(field_name)
                        if expected and response.get(field_name) != expected:
                            raise ValueError(f"model_contract_changed:{field_name}")
            except urllib.error.HTTPError as exc:
                status_code, error = exc.code, f"http_{exc.code}"
                raw_text = exc.read().decode(errors="replace")
                retryable = exc.code in {429, 502, 503, 504}
                response = {"status": "error", "error": error}
            except Exception as exc:
                error = type(exc).__name__ + ":" + str(exc)
                response = {"status": "error", "error": error}
                # A client timeout does not establish that server inference stopped.
                # Never retry uncertain in-flight work automatically.
            elapsed = time.monotonic() - start
            attempts.append({"attempt": attempt + 1, "http_status": status_code, "error": error, "http_latency_s": elapsed, "http_request_body_bytes": len(body), "image_bytes": len(image_bytes), "raw_response": raw_text, "api_cost": 0, "cost_basis": "local_model_no_paid_api"})
            if not retryable or attempt == self.max_retries:
                break
            time.sleep(1)
        value = {"request_id": request_id, "response": response, "attempts": attempts, "effective_latency_s": time.monotonic()-total_start, "image_sha256": digest(image_bytes), "image_bytes": len(image_bytes), "execution_mode": "real_http", "cache_key": key, "api_cost": 0, "cost_basis": "local_model_no_paid_api"}
        cached.write_text(json.dumps(value, ensure_ascii=False))
        return value


def encoded(frame: dict, resolution: int, out: Path) -> Path:
    path = Path(frame["path"])
    if not path.is_absolute():
        path = ROOT / path
    target = out / f"{frame['frame_id']}_{resolution}.jpg"
    metadata_path=target.with_suffix(".json")
    source_hash=digest(path.read_bytes())
    previous=json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    if not target.exists() or previous.get("source_sha256") != source_hash:
        started=time.perf_counter()
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((resolution, resolution), Image.Resampling.LANCZOS)
            image.save(target, quality=82, subsampling=0)
        metadata_path.write_text(json.dumps({"encoding_s":time.perf_counter()-started,"source_path":str(path),"source_sha256":source_hash,"long_edge":resolution,"quality":82,"subsampling":0}))
    return target


def run_policy(frames: list[dict], config: dict, client: Any, output: Path) -> tuple[list[dict], list[dict]]:
    decisions, requests = [], []
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output/"decisions.jsonl",[])
    write_jsonl(output/"requests.jsonl",[])
    videos = sorted({f["video_id"] for f in frames})
    for video_id in videos:
        policy = Policy(**config)
        pending = None
        for frame in sorted((f for f in frames if f["video_id"] == video_id), key=lambda f: f["pts_s"]):
            t = float(frame["pts_s"])
            if pending and pending["completed_at_s"] <= t:
                policy.returned(pending["completed_at_s"], pending["source_pts_s"], pending["features"], pending["response"])
                pending = None
            start = time.perf_counter()
            path = Path(frame["path"])
            if not path.is_absolute():
                path = ROOT / path
            with Image.open(path) as image:
                f = features(image)
            action, reason, extra = policy.decide(t, f, busy=pending is not None)
            compute_ms = (time.perf_counter()-start)*1000
            visible = [r["available_at_s"] for r in policy.public_results]
            decision = {"frame_id": frame["frame_id"], "video_id": video_id, "visit_id": frame.get("visit_id"), "split": frame["split"], "pts_s": t, "action": action, "reason": reason, "brightness": f["brightness"], "sharpness": f["sharpness"], "dhash": f["hash"], "scheduler_compute_ms": compute_ms, "visible_result_times_s": visible, **extra}
            if action != "wait":
                resolution = 720 if action == "low" else 1280
                start_encode = time.perf_counter()
                image_path = encoded(frame, resolution, ROOT / "data/d2/encoded")
                encode_access_s = time.perf_counter()-start_encode
                encoding_metadata=image_path.with_suffix(".json")
                encode_s = json.loads(encoding_metadata.read_text())["encoding_s"] if encoding_metadata.exists() else encode_access_s
                request_id = f"{config['name']}_{frame['frame_id']}_{policy.requests+1}"
                policy.sent(t)
                result = client.call(image_path, request_id)
                # Real HTTP was acquired synchronously, but its contents remain
                # invisible to the policy until this virtual completion event.
                due = t + compute_ms/1000 + encode_s + result["effective_latency_s"]
                row = {**result, "policy": config["name"], "video_id": video_id, "frame_id": frame["frame_id"], "visit_id": frame.get("visit_id"), "split": frame["split"], "source_pts_s": t, "completed_at_s": due, "resolution": resolution, "image_path": str(image_path), "encoding_s": encode_s,"encoding_access_s_not_inference":encode_access_s, "scheduler_compute_ms": compute_ms, "status_at_video_end": "completed" if due <= frame.get("duration_s", math.inf) else "unfinished", "clock_kind": "offline_virtual_with_measured_http_duration"}
                requests.append(row)
                append_jsonl(output/"requests.jsonl",row)
                pending = {"completed_at_s": due, "source_pts_s": t, "features": f, "response": result["response"]}
                decision["request_id"] = request_id
            decisions.append(decision)
            append_jsonl(output/"decisions.jsonl",decision)
    write_jsonl(output / "decisions.jsonl", decisions)
    write_jsonl(output / "requests.jsonl", requests)
    write_jsonl(output / "attempts.jsonl", [{"request_id":r["request_id"],"video_id":r["video_id"],"frame_id":r["frame_id"],"execution_mode":r["execution_mode"],"source_pts_s":r["source_pts_s"],**a} for r in requests for a in r["attempts"]])
    return decisions, requests


def iou(a: list[float], b: list[float]) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = max(0, a[2]-a[0])*max(0, a[3]-a[1])+max(0, b[2]-b[0])*max(0, b[3]-b[1])-overlap
    return overlap/union if union > 0 else 0


def percentile(values: list[float], p: int) -> float | None:
    return float(np.percentile(values, p)) if values else None


def export_cases(frames: list[dict], event_rows: list[dict], requests: list[dict], output: Path) -> None:
    by_frame = {f["frame_id"]:f for f in frames}
    cases = []
    for req in requests:
        if req["response"].get("status") != "ok":
            source = by_frame[req["frame_id"]]
            cases.append({"case_type":"model_failure","request_id":req["request_id"],"frame_id":source["frame_id"],"image_path":source["path"],"source_video":source.get("source_video"),"pts_s":source["pts_s"],"source_pts_s":source.get("source_pts_s"),"status":req["response"].get("status"),"error":req["response"].get("error"),"raw_output":req["response"].get("raw_text"),"evidence":"actual local model output"})
    for event in event_rows:
        if not event["matching_outputs"] or any(m["late_after_visibility_end"] for m in event["matching_outputs"]):
            frame_id = next((x for x in event["source_frames"] if x in by_frame),None)
            if frame_id is None:
                continue
            source=by_frame[frame_id]
            cases.append({"case_type":"proxy_unmatched_event" if not event["matching_outputs"] else "proxy_late_event","event_id":event["event_id"],"frame_id":frame_id,"image_path":source["path"],"source_video":source.get("source_video"),"pts_s":source["pts_s"],"source_pts_s":source.get("source_pts_s"),"class_name":event["class_name"],"start_s":event["start_s"],"end_s":event["end_s"],"matching_outputs":event["matching_outputs"],"truth_kind":"derived_visibility","review_status":"pending","warning":"不是人工确认的风险漏报案例"})
    write_jsonl(output/"failure_cases.jsonl",cases)


def export_summary_csv(path: Path, summaries: list[dict]) -> None:
    names=["policy","logical_requests","new_real_http_requests","recorded_responses_replayed","proxy_events","proxy_recall_2s","proxy_recall_5s","proxy_recall_10s","proxy_recall_20s","proxy_unmatched_predictions","proxy_unjudged_events","proxy_late_after_visibility_end","proxy_stale_answer_ticks","unknown_answer_ticks","answer_coverage","invalid_outputs","failed_requests","unfinished_at_video_end","encoded_image_bytes_all_logical_attempts","actual_http_request_body_bytes","recorded_e2e_p50_s","recorded_e2e_p95_s","scheduler_p50_ms","scheduler_p95_ms","api_cost","evidence_status"]
    with path.open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=names);writer.writeheader()
        for s in summaries:
            row={k:s.get(k) for k in names}
            row.update({f"proxy_recall_{d}s":s["proxy_recall_by_deadline"][str(d)] for d in DEADLINES})
            row.update(invalid_outputs=s["request_status_counts"]["invalid"],failed_requests=s["request_status_counts"]["error"])
            writer.writerow(row)


def evaluate(events: list[dict], decisions: list[dict], requests: list[dict], output: Path, overlap_threshold: float = .3, policy_config: dict | None = None) -> dict:
    events = [e for e in events if e.get("class_name", e.get("category")) in CATEGORIES]
    event_rows, matches, unmatched = [], {}, 0
    request_events = {}
    for req in requests:
        response = req["response"]
        if response.get("status") != "ok" or response.get("result", {}).get("quality_usable") is not True:
            continue
        objects = response["result"].get("objects", [])
        eligible = [(e, ef) for e in events if e["video_id"] == req["video_id"] for ef in e.get("frames", []) if ef["frame_id"] == req["frame_id"]]
        used = set()
        for obj_index, obj in enumerate(objects):
            choices = [(iou(obj.get("bbox", []), ef["bbox"]), e) for e, ef in eligible if e["event_id"] not in used and obj.get("category") == e.get("class_name", e.get("category"))]
            overlap, event = max(choices, key=lambda item:item[0], default=(0, None))
            if event is None or overlap < overlap_threshold:
                unmatched += 1
                continue
            used.add(event["event_id"])
            request_events.setdefault(req["request_id"], []).append(event)
            matches.setdefault(event["event_id"], []).append({"request_id": req["request_id"], "source_frame_id": req["frame_id"], "source_pts_s": req["source_pts_s"], "returned_at_s": req["completed_at_s"], "iou": overlap, "late_after_visibility_end": req["completed_at_s"] > event["end_s"]})
    for event in events:
        hit = matches.get(event["event_id"], [])
        first = min((x["returned_at_s"] for x in hit), default=None)
        statuses = {str(d): bool(first is not None and first <= event["start_s"]+d and first <= event["end_s"]) for d in DEADLINES}
        event_rows.append({"event_id": event["event_id"], "video_id": event["video_id"], "visit_id": event.get("visit_id"), "class_name": event.get("class_name", event.get("category")), "start_s": event["start_s"], "end_s": event["end_s"], "truth_kind": event.get("truth_kind"), "review_status": event.get("review_status"), "first_matched_return_s": first, "timely_by_deadline": statuses, "matching_outputs": hit, "status": "matched_proxy" if hit else "unjudged_proxy", "source_frames": [x["frame_id"] for x in event.get("frames", [])]})
    # Snapshot of retained answer, assessed against derived event visibility.
    # D withdraws answers at its declared source-frame TTL. Withdrawal is
    # recorded as unknown, so low stale counts cannot hide low coverage.
    answer_ticks, stale_ticks, unknown_ticks, ttl_withdrawals = [], 0, 0, 0
    for decision in decisions:
        t = decision["pts_s"]
        returned = [r for r in requests if r["video_id"] == decision["video_id"] and r["completed_at_s"] <= t]
        latest = max(returned, key=lambda r:r["completed_at_s"], default=None)
        expired = bool(latest and policy_config and policy_config.get("kind") == "candidate" and t-latest["source_pts_s"] >= policy_config.get("result_ttl_s",12))
        unknown = latest is None or expired or latest["response"].get("status") != "ok" or latest["response"].get("result",{}).get("quality_usable") is not True
        stale = bool(not unknown and any(t > e["end_s"] for e in request_events.get(latest["request_id"],[])))
        unknown_ticks += int(unknown); stale_ticks += int(stale); ttl_withdrawals += int(expired)
        answer_ticks.append({"frame_id":decision["frame_id"],"pts_s":t,"video_id":decision["video_id"],"retained_request_id":latest["request_id"] if latest else None,"unknown":unknown,"withdrawn_due_to_ttl":expired,"proxy_stale":stale,"truth_kind":"derived_visibility","review_status":"pending"})
    write_jsonl(output/"answer_ticks.jsonl",answer_ticks)
    logical_latencies = [r["completed_at_s"]-r["source_pts_s"] for r in requests]
    usable = [r for r in requests if r["response"].get("status") == "ok" and (r["response"].get("result") or {}).get("quality_usable") is True and r["status_at_video_end"] == "completed"]
    usable_latencies = [r["completed_at_s"]-r["source_pts_s"] for r in usable]
    actual = [r for r in requests if r["execution_mode"] == "real_http"]
    status_counts = {s: sum(r["response"].get("status") == s for r in requests) for s in ("ok", "invalid", "error")}
    per_class = {}
    for category in sorted(CATEGORIES):
        rows = [e for e in event_rows if e["class_name"] == category]
        per_class[category] = {"n": len(rows), "proxy_recall_by_deadline": {str(d): sum(e["timely_by_deadline"][str(d)] for e in rows)/len(rows) if rows else None for d in DEADLINES}}
    summary = {"evidence_status": "exploratory_real_model_on_derived_visibility_labels", "human_reviewed_event_metrics": "未测", "risk_or_critical_category_recall": "未测", "noninferiority": "未测", "proxy_truth_review_status": "pending", "deadline_seconds": list(DEADLINES), "bbox_iou_threshold": overlap_threshold, "proxy_events": len(events), "proxy_recall_by_deadline": {str(d): sum(e["timely_by_deadline"][str(d)] for e in event_rows)/len(event_rows) if event_rows else None for d in DEADLINES}, "per_class": per_class, "proxy_unmatched_predictions": unmatched, "proxy_unjudged_events": sum(not e["matching_outputs"] for e in event_rows), "proxy_late_after_visibility_end": sum(m["late_after_visibility_end"] for hit in matches.values() for m in hit), "ticks": len(decisions), "logical_requests": len(requests), "logical_attempts_including_replays": sum(len(r["attempts"]) for r in requests), "new_real_http_requests": len(actual), "new_real_http_attempts": sum(len(r["attempts"]) for r in actual), "recorded_responses_replayed": len(requests)-len(actual), "encoded_image_bytes_all_logical_attempts": sum(r["image_bytes"]*len(r["attempts"]) for r in requests), "actual_http_request_body_bytes": sum(a["http_request_body_bytes"] for r in actual for a in r["attempts"]), "counterfactual_http_body_bytes_all_logical_attempts": sum(a["http_request_body_bytes"] for r in requests for a in r["attempts"]), "api_cost": 0, "api_cost_savings_percent": None, "cost_note": "本地模型无付费API；不含电费/设备折旧，不能由调用下降推断节省金额", "request_status_counts": status_counts, "unfinished_at_video_end": sum(r["status_at_video_end"] == "unfinished" for r in requests), "recorded_e2e_p50_s": percentile(logical_latencies,50), "recorded_e2e_p95_s": percentile(logical_latencies,95), "new_actual_http_p50_s": percentile([a["http_latency_s"] for r in actual for a in r["attempts"]],50), "new_actual_http_p95_s": percentile([a["http_latency_s"] for r in actual for a in r["attempts"]],95), "scheduler_p50_ms": percentile([d["scheduler_compute_ms"] for d in decisions],50), "scheduler_p95_ms": percentile([d["scheduler_compute_ms"] for d in decisions],95), "reason_counts": {reason: sum(d["reason"] == reason for d in decisions) for reason in sorted({d["reason"] for d in decisions})}}
    summary.update(proxy_stale_answer_ticks=stale_ticks, unknown_answer_ticks=unknown_ticks, answer_coverage=(len(decisions)-unknown_ticks)/len(decisions) if decisions else None, ttl_withdrawal_ticks=ttl_withdrawals)
    summary.update(usable_completed_requests=len(usable), usable_completion_rate=len(usable)/len(requests) if requests else None, usable_response_conditional_p50_s=percentile(usable_latencies,50), usable_response_conditional_p95_s=percentile(usable_latencies,95), all_request_usable_result_p50_s=percentile(usable_latencies,50) if len(usable)==len(requests) else None, all_request_usable_result_p95_s=percentile(usable_latencies,95) if len(usable)==len(requests) else None, usable_latency_note="Conditional quantiles include only valid quality-usable responses completed within video; all-request usable quantiles are conservatively null if any failed/invalid/unusable/unfinished request. recorded_e2e quantiles measure request termination, not usable answers.")
    write_jsonl(output / "events.jsonl", event_rows)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def policy_configs() -> list[dict]:
    return [
        {"name":"A_fixed", "kind":"fixed", "interval_s":6, "resolution":720, "maximum_requests":30},
        {"name":"B_original", "kind":"original", "interval_s":6, "hash_threshold":6, "resolution":720, "maximum_requests":30},
        {"name":"C_fix", "kind":"fixed_gate", "interval_s":6, "hash_threshold":6, "resolution":720, "maximum_requests":30},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=ROOT/"data/d2/frames.jsonl")
    parser.add_argument("--events", type=Path, default=ROOT/"data/d2/proxy_events.jsonl")
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765/analyze")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--path-only", action="store_true")
    parser.add_argument("--no-cache", action="store_true", help="Execute every request; independent measured HTTP run")
    parser.add_argument("--run-tag", default="", help="Keep separate exploratory/probe runs out of dev/test outputs")
    parser.add_argument("--max-frames", type=int, default=0, help="Debug only; never label as full experiment")
    parser.add_argument("--policy", help="Comma separated names; debug/exploration only")
    args = parser.parse_args()
    all_frames=read_jsonl(args.frames)
    validate_manifest(all_frames)
    frames = [f for f in all_frames if f["split"] == args.split]
    if not frames:
        raise SystemExit("No frames: real research result remains unmeasured")
    if args.max_frames:
        frames = frames[:args.max_frames]
    frame_ids = {f["frame_id"] for f in frames}
    events = [e for e in read_jsonl(args.events) if e["split"] == args.split and any(f["frame_id"] in frame_ids for f in e.get("frames", []))]
    contract = json.loads(args.contract.read_text())
    output = ROOT/"runs/d2"/(args.run_tag or args.split)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output/"input_frames.jsonl",frames)
    write_jsonl(output/"input_events.jsonl",events)
    run_manifest = {"split":args.split,"code_sha256":digest(Path(__file__).read_bytes()),"input_frames_sha256":digest((output/"input_frames.jsonl").read_bytes()),"input_events_sha256":digest((output/"input_events.jsonl").read_bytes()),"model_contract":contract,"timeout_s":args.timeout,"frames":len(frames),"videos":sorted({f["video_id"] for f in frames}),"truth_kind":"derived_visibility","human_review_status":"pending","endpoint":args.endpoint,"started_unix_s":time.time(),"max_frames_debug_limit":args.max_frames or None}
    (output/"run_manifest.json").write_text(json.dumps(run_manifest,ensure_ascii=False,indent=2))
    configs = policy_configs()
    freeze = ROOT/"configs/d2_frozen.json"
    if args.split == "dev":
        configs += [{"name":f"C_tune_i{i}_h{h}_r{r}", "kind":"fixed_gate", "interval_s":i, "hash_threshold":h, "resolution":r, "maximum_requests":30} for i,h,r in [(3,4,720),(6,6,720),(3,4,1280),(6,6,1280)]]
        configs += [{"name":f"D_tune_s{s}", "kind":"candidate", "interval_s":3, "hash_threshold":4, "max_silence_s":s, "result_ttl_s":s, "local_threshold":.12, "maximum_requests":30} for s in (6,12)]
    else:
        if not freeze.exists():
            raise SystemExit("Development freeze required before test")
        frozen = json.loads(freeze.read_text())
        if frozen["model_contract"] != contract:
            raise SystemExit("Model contract differs from frozen development contract")
        if frozen["timeout_s"] != args.timeout:
            raise SystemExit("Timeout differs from frozen development timeout")
        if frozen["code_sha256"] != digest(Path(__file__).read_bytes()):
            raise SystemExit("Scheduler/evaluator changed after development freeze; use a separately named exploratory run")
        configs += frozen["selected_configs"]
    if args.policy:
        configs = [c for c in configs if c["name"] in args.policy.split(",")]
    client = HTTPModel(args.endpoint, ROOT/"runs/d2/response_cache", contract, args.timeout, send_image=not args.path_only, use_cache=not args.no_cache)
    summaries = []
    for config in configs:
        path = output/config["name"]
        path.mkdir(parents=True, exist_ok=True)
        (path/"config.json").write_text(json.dumps(config, indent=2))
        print(json.dumps({"stage":"start_policy", "split":args.split, "policy":config["name"], "frames":len(frames)}, ensure_ascii=False), flush=True)
        decisions, requests = run_policy(frames, config, client, path)
        summary = evaluate(events, decisions, requests, path, policy_config=config)
        export_cases(frames,read_jsonl(path/"events.jsonl"),requests,path)
        summary["run_mode"] = "independent_real_http_driven_offline_replay" if args.no_cache else "real_http_and_recorded_response_driven_offline_replay"
        summary["max_frames_debug_limit"] = args.max_frames or None
        (path/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        summaries.append({"policy":config["name"], **summary})
        print(json.dumps({"stage":"completed_policy", "policy":config["name"], "requests":len(requests), "new_real":summary["new_real_http_requests"], "proxy_recall":summary["proxy_recall_by_deadline"]}, ensure_ascii=False), flush=True)
    write_jsonl(output/"summary.jsonl", summaries)
    export_summary_csv(output/"summary.csv",summaries)
    if args.split == "dev" and not args.policy and not args.max_frames and not args.run_tag:
        def select(prefix: str) -> dict:
            candidates = [s for s in summaries if s["policy"].startswith(prefix)]
            # Exploratory dev-only proxy selection: retain highest 20s recall,
            # then highest 5s recall, then minimum requests/bytes.
            best = max(candidates, key=lambda s:(s["proxy_recall_by_deadline"]["20"] or 0, s["proxy_recall_by_deadline"]["5"] or 0, -s["logical_requests"], -s["encoded_image_bytes_all_logical_attempts"]))
            result = dict(next(c for c in configs if c["name"] == best["policy"]))
            result["name"] = "C_tuned" if prefix == "C_tune" else "D_candidate"
            return result
        frozen = {"created_unix_s":time.time(), "selection_basis":"development-derived-visibility-only, maximize recall20 then recall5 then minimize logical calls/bytes; exploratory, no approved quality threshold", "model_contract":contract, "timeout_s":args.timeout, "selected_configs":[select("C_tune"), select("D_tune")], "frames_sha256":run_manifest["input_frames_sha256"], "events_sha256":run_manifest["input_events_sha256"], "development_frame_ids_sha256":digest(sorted(frame_ids)), "development_videos":run_manifest["videos"],"development_frame_count":len(frames),"code_sha256":run_manifest["code_sha256"], "deadlines_s":list(DEADLINES)}
        freeze.write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
        print(f"Frozen dev choices: {freeze}", flush=True)


if __name__ == "__main__":
    main()
