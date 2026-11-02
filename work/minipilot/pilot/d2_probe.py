"""Independent, uncached HTTP timing check on a fixed development prefix.

This is an engineering repeat, not a second held-out quality experiment. Every
policy gets new JPEG encoding and fresh model requests. No event labels are read.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import d2


def main() -> None:
    destination = d2.ROOT / "runs/d2/independent_http_probe"
    destination.mkdir(parents=True, exist_ok=False)
    contract = json.loads((d2.ROOT / "configs/d2_model_contract.json").read_text())
    frozen = json.loads((d2.ROOT / "configs/d2_frozen.json").read_text())
    assert frozen["code_sha256"] == d2.digest(Path(d2.__file__).read_bytes())
    frames = [f for f in d2.read_jsonl(d2.ROOT / "data/d2/frames.jsonl")
              if f["split"] == "dev" and f["video_id"] == "40777060" and f["pts_s"] <= 20]
    d2.write_jsonl(destination / "input_frames.jsonl", frames)
    configs = d2.policy_configs() + frozen["selected_configs"]
    original_encode = d2.encoded
    summaries = []
    for config in configs:
        output = destination / config["name"]
        output.mkdir()
        # Separate each policy's encodings as well as all response caches.
        d2.encoded = lambda frame, resolution, ignored: original_encode(frame, resolution, output / "encoded")
        client = d2.HTTPModel("http://127.0.0.1:8765/analyze", output / "responses", contract,
                              timeout_s=60, max_retries=1, use_cache=False)
        wall_start = time.monotonic()
        decisions, requests = d2.run_policy(frames, config, client, output)
        usable = [r for r in requests if r["response"].get("status") == "ok"
                  and (r["response"].get("result") or {}).get("quality_usable") is True]
        e2e = [r["completed_at_s"] - r["source_pts_s"] for r in usable]
        http = [a["http_latency_s"] for r in requests for a in r["attempts"]]
        row = {"policy": config["name"], "config": config, "frame_count": len(frames),
               "requests": len(requests), "usable_responses": len(usable),
               "status_counts": {s: sum(r["response"].get("status") == s for r in requests)
                                 for s in ("ok", "invalid", "error")},
               "actual_http_p50_s": d2.percentile(http, 50), "actual_http_p95_s": d2.percentile(http, 95),
               "usable_e2e_conditional_p50_s": d2.percentile(e2e, 50),
               "usable_e2e_conditional_p95_s": d2.percentile(e2e, 95),
               "actual_http_request_body_bytes": sum(a["http_request_body_bytes"] for r in requests for a in r["attempts"]),
               "wall_clock_execution_s": time.monotonic() - wall_start, "api_cost": 0,
               "evidence_status": "independent_uncached_actual_http_technical_repeat_on_dev_prefix",
               "warning": "Few requests; descriptive timing only. Not original-speed live replay, no quality or cost-savings inference."}
        (output / "summary.json").write_text(json.dumps(row, ensure_ascii=False, indent=2))
        summaries.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    d2.encoded = original_encode
    d2.write_jsonl(destination / "summary.jsonl", summaries)
    (destination / "manifest.json").write_text(json.dumps({"created_unix_s": time.time(),
        "model_contract": contract, "d2_sha256": frozen["code_sha256"],
        "input_frames_sha256": d2.digest((destination / "input_frames.jsonl").read_bytes()),
        "frame_selection": "development video 40777060, PTS <=20 seconds",
        "event_labels_read": False, "cache_reused": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
