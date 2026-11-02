"""ARKitScenes public-data acquisition and provenance-preserving replay inputs.

Derived visibility is a draft reference, never independently reviewed event truth.
No reference annotation is stored in frames.jsonl (the scheduler input).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"
VIDEOS = [
    ("Training", "369709", "40777060", "dev"),
    ("Training", "369709", "40777063", "dev"),
    ("Validation", "381649", "41069042", "test"),
    ("Validation", "381649", "41069043", "test"),
    ("Validation", "381875", "41159529", "test"),
    ("Validation", "381875", "41159530", "test"),
]
CATEGORY_MAP = {"chair": "chair", "table": "table", "desk": "table", "sofa": "sofa", "couch": "sofa", "cabinet": "cabinet", "bed": "bed", "shelf": "shelf", "bookcase": "shelf"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def download_one(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    record = {"url": url, "path": str(path.relative_to(ROOT)), "started_unix": start}
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            expected = int(resp.headers.get("Content-Length", 0))
            record.update(expected_bytes=expected, etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"))
        partial = path.with_suffix(path.suffix + ".partial")
        if not path.exists() or (expected and path.stat().st_size != expected):
            if path.exists():
                path.replace(partial)
            result = subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--retry-delay", "1", "--connect-timeout", "30", "--max-time", "1800", "--continue-at", "-", "--silent", "--show-error", "--output", str(partial), url], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr[-2000:])
            if expected and partial.stat().st_size != expected:
                raise ValueError("Downloaded byte count differs from Content-Length")
            partial.replace(path)
        record.update(status="complete", bytes=path.stat().st_size, sha256=sha256(path))
    except Exception as exc:
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    record["elapsed_s"] = time.time() - start
    return record


def download_ranges(url, path, workers=8, chunk_bytes=4 * 1024 * 1024):
    """Resumable byte-range download; validates every returned range and length."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as resp:
        total = int(resp.headers["Content-Length"])
        etag = resp.headers.get("ETag")
    if path.exists() and path.stat().st_size == total:
        return {"url": url, "path": str(path.relative_to(ROOT)), "status": "complete", "bytes": total, "sha256": sha256(path), "reused": True}
    partial = path.with_suffix(path.suffix + ".partial")
    prefix = partial.stat().st_size if partial.exists() else 0
    if prefix > total:
        raise ValueError("Partial exceeds remote size")
    chunkdir = path.with_suffix(path.suffix + ".chunks")
    chunkdir.mkdir(exist_ok=True)
    def get_chunk(bounds):
        lo, hi = bounds
        out = chunkdir / f"{lo}-{hi}"
        if out.exists() and out.stat().st_size == hi - lo + 1:
            return out
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={lo}-{hi}"})
                with urllib.request.urlopen(req, timeout=90) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {lo}-{hi}/{total}":
                        raise ValueError("Server did not honor requested byte range")
                    data = response.read()
                if len(data) != hi - lo + 1:
                    raise ValueError("Short range response")
                tmp = out.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(out)
                return out
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1 + attempt)
    ranges = [(lo, min(lo + chunk_bytes - 1, total - 1)) for lo in range(prefix, total, chunk_bytes)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        chunks = list(executor.map(get_chunk, ranges))
    with partial.open("ab") as dst:
        for p in chunks:
            with p.open("rb") as src:
                for data in iter(lambda: src.read(8 * 1024 * 1024), b""):
                    dst.write(data)
    if partial.stat().st_size != total:
        raise ValueError("Assembled range size mismatch")
    partial.replace(path)
    for p in chunks:
        p.unlink()
    try:
        chunkdir.rmdir()
    except OSError:
        pass
    return {"url": url, "path": str(path.relative_to(ROOT)), "status": "complete", "bytes": total, "sha256": sha256(path), "etag": etag, "elapsed_s": time.time() - started, "download_method": "validated_http_ranges", "workers": workers, "resumed_prefix_bytes": prefix}


def download(video_ids=None, mov=True, sparse=True, range_workers=0):
    jobs = []
    for fold, visit, vid, split in VIDEOS:
        if video_ids and vid not in video_ids:
            continue
        folder = ROOT / "data/d2/raw" / vid
        if mov:
            jobs.append((f"{BASE}/raw/{fold}/{vid}/{vid}.mov", folder / f"{vid}.mov"))
        if sparse:
            jobs.append((f"{BASE}/threedod/{fold}/{vid}.zip", folder / f"{vid}_3dod.zip"))
        jobs.append((f"{BASE}/raw/{fold}/{vid}/{vid}_3dod_annotation.json", folder / f"{vid}_3dod_annotation.json"))
    sources = [
        (f"{BASE}/raw/metadata.csv", ROOT / "data/d2/source_metadata.csv"),
        ("https://raw.githubusercontent.com/apple-aiml-research/ARKitScenes/main/LICENSE", ROOT / "data/d2/LICENSE_ARKitScenes.txt"),
        ("https://raw.githubusercontent.com/apple-aiml-research/ARKitScenes/main/threedod/benchmark_scripts/utils/tenFpsDataLoader.py", ROOT / "data/d2/reference_tenFpsDataLoader.py.txt"),
        ("https://raw.githubusercontent.com/apple-aiml-research/ARKitScenes/main/threedod/benchmark_scripts/utils/box_utils.py", ROOT / "data/d2/reference_box_utils.py.txt"),
    ]
    jobs.extend(sources)
    log = ROOT / "runs/d2_data/downloads.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if range_workers else 2) as ex:
        pending = [ex.submit(download_ranges, *j, range_workers) if range_workers and j[1].suffix in {".mov", ".zip"} else ex.submit(download_one, *j) for j in jobs]
        for future in concurrent.futures.as_completed(pending):
            record = future.result()
            records.append(record)
            with log.open("a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(json.dumps(record, ensure_ascii=False), flush=True)
    write_json(ROOT / "docs/data_sources.json", {
        "dataset": "ARKitScenes", "source_kind": "public_real_indoor_recordings", "repository": "https://github.com/apple-aiml-research/ARKitScenes", "license_url": "https://github.com/apple-aiml-research/ARKitScenes/blob/main/LICENSE", "paper_url": "https://arxiv.org/html/2111.08897v1", "download_manifest": "runs/d2_data/downloads.jsonl", "selection": [dict(official_split=f, visit_id=v, video_id=i, split=s) for f, v, i, s in VIDEOS], "split_rule": "Official Training is dev; official Validation is held-out test. Repeated scans retain visit group. No household identity beyond official split is asserted.", "limitations": ["Static furniture, not cable/box risk events", "Two videos are repeated scans, not independent layouts", "Derived event visibility requires independent human review", "Source metadata has no explicit household ID", "Evaluation references must never enter scheduler state"]})
    return records


def probe_video(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration,start_time,size:stream=width,height,avg_frame_rate,start_time,time_base:stream_tags:stream_side_data", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def choose_frame_indices(times, interval=1.0):
    """First available source frame at/after each integral replay tick, no fake PTS."""
    if not times:
        return []
    origin = times[0]
    selected, tick = [], 0
    for i, pts in enumerate(times):
        if pts + 1e-8 >= origin + tick * interval:
            selected.append(i)
            tick = int((pts - origin + 1e-8) / interval) + 1
    return selected


def extract_one(fold, visit, vid, split):
    video = ROOT / "data/d2/raw" / vid / f"{vid}.mov"
    if not video.exists():
        return {"video_id": vid, "status": "unavailable", "reason": "MOV not downloaded"}
    folder = ROOT / "data/d2/frames" / vid
    folder.mkdir(parents=True, exist_ok=True)
    metadata = probe_video(video)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(video)], capture_output=True, text=True, check=True)
    pts = [float(x["best_effort_timestamp_time"]) for x in json.loads(probe.stdout)["frames"] if "best_effort_timestamp_time" in x]
    indices = choose_frame_indices(pts)
    expression = "+".join(f"eq(n\\,{i})" for i in indices)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-y", "-noautorotate", "-i", str(video), "-map", "0:v:0", "-vf", f"select={expression},scale=1280:-2,showinfo", "-fps_mode", "passthrough", "-q:v", "2", str(folder / "%06d.jpg")]
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    (ROOT / "runs/d2_data").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs/d2_data" / f"extract_{vid}.log").write_text(result.stderr)
    if result.returncode:
        return {"video_id": vid, "status": "failed", "error": result.stderr[-2000:]}
    from PIL import Image
    rows = []
    for j, source_index in enumerate(indices, 1):
        path = folder / f"{j:06d}.jpg"
        if not path.exists():
            raise ValueError(f"Missing output frame: {path}")
        with Image.open(path) as im:
            width, height = im.size
            im.verify()
        rows.append({"frame_id": f"{vid}_{j:06d}", "video_id": vid, "visit_id": visit, "site_id": visit, "split": split, "official_split": fold, "pts_s": pts[source_index] - pts[0], "t_s": pts[source_index] - pts[0], "source_pts_s": pts[source_index], "source_frame_index": source_index, "path": str(path.relative_to(ROOT)), "width": width, "height": height, "duration_s": float(metadata["format"]["duration"]), "source_width": metadata["streams"][0]["width"], "source_height": metadata["streams"][0]["height"], "source_video": str(video.relative_to(ROOT)), "image_sha256": sha256(path), "truth_kind": "real_rgb_frame", "autorotate": False})
    write_jsonl(ROOT / "data/d2" / f"frames_{vid}.jsonl", rows)
    write_json(ROOT / "runs/d2_data" / f"metadata_{vid}.json", {"probe": metadata, "extraction_command": command, "source_sha256": sha256(video), "sample_rule": "first source frame at or after each integral second", "origin_source_pts_s": pts[0], "frame_count": len(rows), "extract_wall_s": time.monotonic() - start})
    return {"video_id": vid, "status": "complete", "frames": len(rows)}


def rotate_bbox(bbox, angle):
    """Normalized xyxy under PIL's counterclockwise positive display rotation."""
    x0, y0, x1, y1 = bbox
    angle = int(angle) % 360
    if angle == 0:
        return list(bbox)
    if angle == 90:
        return [y0, 1 - x1, y1, 1 - x0]
    if angle == 180:
        return [1 - x1, 1 - y1, 1 - x0, 1 - y0]
    if angle == 270:
        return [1 - y1, x0, 1 - y0, x1]
    raise ValueError("Only right-angle metadata rotations supported")


def normalize_orientation(vid):
    from PIL import Image
    manifest = ROOT / "data/d2" / f"frames_{vid}.jsonl"
    metadata = json.loads((ROOT / "runs/d2_data" / f"metadata_{vid}.json").read_text())
    side_data = metadata["probe"]["streams"][0].get("side_data_list", [])
    angle = next((float(s["rotation"]) for s in side_data if "rotation" in s), 0)
    if angle % 90 != 0:
        raise ValueError(f"Unexpected display rotation: {angle}")
    rows = [json.loads(x) for x in manifest.read_text().splitlines()]
    folder = ROOT / "data/d2/upright" / vid
    folder.mkdir(parents=True, exist_ok=True)
    for f in rows:
        raw = ROOT / f.get("raw_frame_path", f["path"])
        dest = folder / raw.name
        with Image.open(raw) as im:
            upright = im.rotate(angle, expand=True)
            upright.save(dest, quality=95)
            f["width"], f["height"] = upright.size
        f.update(raw_frame_path=str(raw.relative_to(ROOT)), raw_frame_sha256=sha256(raw), path=str(dest.relative_to(ROOT)), image_sha256=sha256(dest), display_rotation_degrees=angle, orientation_normalization="MOV Display Matrix rotation applied, independent of predictions")
    write_jsonl(manifest, rows)


def extract(video_ids=None):
    statuses = []
    for item in VIDEOS:
        if video_ids and item[2] not in video_ids:
            continue
        status = extract_one(*item)
        if status["status"] == "complete":
            normalize_orientation(item[2])
        statuses.append(status)
        print(json.dumps(status), flush=True)
        rows = []
        for p in sorted((ROOT / "data/d2").glob("frames_*.jsonl")):
            rows.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
        write_jsonl(ROOT / "data/d2/frames.jsonl", rows)
    write_json(ROOT / "runs/d2_data/extraction_status.json", statuses)


def unpack(video_ids=None):
    for _, _, vid, _ in VIDEOS:
        if video_ids and vid not in video_ids:
            continue
        path = ROOT / "data/d2/raw" / vid / f"{vid}_3dod.zip"
        if path.exists():
            target = ROOT / "data/d2/sparse" / vid
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path) as z:
                for member in z.infolist():
                    dst = (target / member.filename).resolve()
                    if not dst.is_relative_to(target.resolve()):
                        raise ValueError("Unsafe ZIP member")
                z.extractall(target)
            print(json.dumps({"video_id": vid, "unpacked": str(target)}), flush=True)


def image_vector(path):
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        v = np.asarray(im.convert("RGB").resize((64, 48), Image.Resampling.BILINEAR), dtype=float).reshape(-1)
    v -= v.mean()
    return v / max(float(np.linalg.norm(v)), 1e-9)


def align_sparse_clock(frames, rgb_files):
    """Estimate clock offset from corresponding real RGB, with an explicit gate.

    This is an annotation-only synchronization diagnostic. It never influences
    scheduling, model requests, or the development/test split.
    """
    import numpy as np
    times = np.array([float(p.stem.split("_")[-1]) for p in rgb_files])
    refs = np.stack([image_vector(p) for p in rgb_files])
    query = np.stack([image_vector(ROOT / f.get("raw_frame_path", f["path"])) for f in frames])
    similarity = query @ refs.T
    best = similarity.argmax(axis=1)
    confidence = similarity[np.arange(len(frames)), best]
    replay = np.array([f["pts_s"] for f in frames])
    differences = times[best] - replay
    usable = confidence >= .94
    if usable.sum() < max(5, len(frames) // 3):
        return {"status": "unavailable", "reason": "Insufficient RGB correspondences for clock synchronization", "high_similarity_frames": int(usable.sum())}, []
    initial = float(np.median(differences[usable]))
    inliers = usable & (np.abs(differences - initial) <= .2)
    offset = float(np.median(differences[inliers]))
    residual = np.abs(differences[inliers] - offset)
    accepted = int(inliers.sum()) >= max(5, len(frames) // 2) and float(np.median(residual)) <= .075
    matches = []
    for i, frame in enumerate(frames):
        # Nearest official timestamp to the independently fitted source clock.
        j = int(np.argmin(np.abs(times - (replay[i] + offset))))
        dt = float(times[j] - (replay[i] + offset))
        sim = float(similarity[i, j])
        matches.append({"frame_id": frame["frame_id"], "pts_s": frame["pts_s"], "source_timestamp_s": float(times[j]), "sparse_rgb_path": str(rgb_files[j].relative_to(ROOT)), "clock_residual_s": dt, "rgb_cosine_similarity": sim, "valid": bool(accepted and abs(dt) <= .075 and sim >= .94)})
    return {"status": "aligned" if accepted else "unavailable", "method": "median RGB matched timestamp offset with robust inlier gate", "offset_s": offset, "inlier_count": int(inliers.sum()), "frame_count": len(frames), "median_abs_residual_s": float(np.median(residual)), "median_rgb_similarity": float(np.median(confidence)), "valid_matches": sum(x["valid"] for x in matches), "independently_reviewed": False}, matches


def depth_points_world(depth_m, intrinsic, world_to_camera):
    import numpy as np
    h, w = depth_m.shape
    yy, xx = np.mgrid[:h, :w]
    valid = np.isfinite(depth_m) & (depth_m > 0) & (depth_m < 20)
    z = depth_m[valid]
    camera = np.stack([(xx[valid] - intrinsic[0, 2]) * z / intrinsic[0, 0], (yy[valid] - intrinsic[1, 2]) * z / intrinsic[1, 1], z], axis=1)
    points = (camera - world_to_camera[:3, 3]) @ world_to_camera[:3, :3]
    return points, xx[valid], yy[valid]


def box_pixel_support(points, xx, yy, annotation, width, height, min_points=21):
    import numpy as np
    box = annotation["segments"]["obbAligned"]
    rotation = np.asarray(box["normalizedAxes"], dtype=float).reshape(3, 3)
    size = np.asarray(box["axesLengths"], dtype=float)
    center = np.asarray(box["centroid"], dtype=float)
    local = (points - center) @ rotation.T
    inside = np.all(np.abs(local) <= size / 2 + .01, axis=1)
    count = int(inside.sum())
    if count < min_points:
        return None
    x0, x1 = int(xx[inside].min()), int(xx[inside].max()) + 1
    y0, y1 = int(yy[inside].min()), int(yy[inside].max()) + 1
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    return {"bbox": [x0 / width, y0 / height, x1 / width, y1 / height], "support_depth_points": count, "support_rule": "valid measured depth pixels inside official oriented 3D box; >=21 pixels, >=3px extent", "occlusion_handling": "Only actually observed depth points contribute; this is not a human visibility judgment"}


def contiguous_events(observations, duration_s):
    """No filling of unsupported frame gaps; every segment remains a draft."""
    by_object = {}
    for row in observations:
        by_object.setdefault(row["object_uid"], []).append(row)
    events = []
    for uid, rows in by_object.items():
        rows.sort(key=lambda r: r["pts_s"])
        groups = [[]]
        for row in rows:
            if groups[-1] and row["pts_s"] - groups[-1][-1]["pts_s"] > 1.1:
                groups.append([])
            groups[-1].append(row)
        for number, group in enumerate(groups, 1):
            first = group[0]
            events.append({"event_id": f"{first['video_id']}_{uid}_{number:02d}", "video_id": first["video_id"], "visit_id": first["visit_id"], "site_id": first["visit_id"], "split": first["split"], "object_uid": uid, "class_name": first["class_name"], "category": first["class_name"], "original_class": first["original_class"], "start_s": first["pts_s"], "end_s": min(duration_s, group[-1]["pts_s"] + 1.0), "start_definition": "first sampled frame meeting automatic depth-support proxy", "end_definition": "last supported sampled frame plus one sampling interval, capped at video duration", "first_sufficiently_judgable_s": None, "truth_kind": "derived_visibility", "review_status": "pending", "critical_category": None, "state_change": "visibility_due_to_camera_motion", "frames": [{k: r[k] for k in ["frame_id", "pts_s", "bbox", "support_depth_points"]} for r in group]})
    return events


def proxy_one(vid):
    import numpy as np
    import cv2
    from PIL import Image
    manifest = ROOT / "data/d2" / f"frames_{vid}.jsonl"
    if not manifest.exists():
        return {"video_id": vid, "status": "unavailable", "reason": "No extracted RGB frames"}
    frames = [json.loads(x) for x in manifest.read_text().splitlines()]
    sparse = ROOT / "data/d2/sparse" / vid / vid
    source = sparse / f"{vid}_frames"
    rgb_files = sorted((source / "lowres_wide").glob("*.png"), key=lambda p: float(p.stem.split("_")[-1]))
    if not rgb_files:
        return {"video_id": vid, "status": "unavailable", "reason": "No official sparse RGB/depth/pose data"}
    alignment, matches = align_sparse_clock(frames, rgb_files)
    write_json(ROOT / "runs/d2_data" / f"clock_alignment_{vid}.json", alignment)
    write_jsonl(ROOT / "runs/d2_data" / f"clock_matches_{vid}.jsonl", matches)
    if alignment["status"] != "aligned":
        return {"video_id": vid, **alignment}
    annotations = json.loads((sparse / f"{vid}_3dod_annotation.json").read_text())["data"]
    included = [a for a in annotations if a["label"] in CATEGORY_MAP]
    poses = np.loadtxt(source / "lowres_wide.traj")
    observations, skipped = [], []
    for frame, match in zip(frames, matches):
        if not match["valid"]:
            skipped.append({"frame_id": frame["frame_id"], "reason": "RGB/clock alignment gate failed"})
            continue
        rgb = ROOT / match["sparse_rgb_path"]
        depth_path = source / "lowres_depth" / rgb.name
        intrinsic_path = source / "lowres_wide_intrinsics" / (rgb.stem + ".pincam")
        if not depth_path.exists() or not intrinsic_path.exists():
            skipped.append({"frame_id": frame["frame_id"], "reason": "Missing synchronized depth or intrinsics"})
            continue
        pose = poses[np.argmin(np.abs(poses[:, 0] - match["source_timestamp_s"]))]
        if abs(float(pose[0]) - match["source_timestamp_s"]) > .006:
            skipped.append({"frame_id": frame["frame_id"], "reason": "Pose timestamp mismatch >6ms"})
            continue
        w, h, fx, fy, cx, cy = np.loadtxt(intrinsic_path)
        intrinsic = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
        world_to_camera = np.eye(4)
        world_to_camera[:3, :3] = cv2.Rodrigues(pose[1:4])[0]
        world_to_camera[:3, 3] = pose[4:7]
        with Image.open(depth_path) as image:
            depth = np.asarray(image, dtype=float) / 1000.0
        if depth.shape != (int(h), int(w)):
            skipped.append({"frame_id": frame["frame_id"], "reason": "Depth/intrinsic resolution mismatch"})
            continue
        points, xx, yy = depth_points_world(depth, intrinsic, world_to_camera)
        for annotation in included:
            support = box_pixel_support(points, xx, yy, annotation, int(w), int(h))
            if support:
                support["raw_bbox"] = support["bbox"]
                support["bbox"] = rotate_bbox(support["bbox"], frame.get("display_rotation_degrees", 0))
                observations.append({"frame_id": frame["frame_id"], "video_id": vid, "visit_id": frame["visit_id"], "split": frame["split"], "pts_s": frame["pts_s"], "class_name": CATEGORY_MAP[annotation["label"]], "original_class": annotation["label"], "object_uid": annotation["uid"], "truth_kind": "derived_visibility", "review_status": "pending", "source_timestamp_s": match["source_timestamp_s"], "rgb_cosine_similarity": match["rgb_cosine_similarity"], **support})
    events = contiguous_events(observations, frames[0]["duration_s"])
    write_jsonl(ROOT / "data/d2" / f"proxy_observations_{vid}.jsonl", observations)
    write_jsonl(ROOT / "data/d2" / f"proxy_events_{vid}.jsonl", events)
    status = {"video_id": vid, "status": "proxy_draft", "events": len(events), "observations": len(observations), "frames": len(frames), "reviewed_events": 0, "clock_alignment": alignment, "skipped_frames": skipped, "excluded_annotation_categories": sorted({a["label"] for a in annotations if a["label"] not in CATEGORY_MAP}), "geometry_source": "Official obbAligned meters and world-to-camera Rodrigues extrinsics; observed depth divided by 1000", "warning": "These are derived furniture visibility proxies, not human risk/event truth or formal earliest-detectable times"}
    write_json(ROOT / "runs/d2_data" / f"proxy_status_{vid}.json", status)
    return status


def render_review(events, frames):
    by_id = {f["frame_id"]: f for f in frames}
    cards = []
    for event in events:
        samples = [event["frames"][i] for i in sorted({0, len(event["frames"]) // 2, len(event["frames"]) - 1})]
        images = []
        for sample in samples:
            f = by_id[sample["frame_id"]]
            x0, y0, x1, y1 = sample["bbox"]
            rel = os.path.relpath(ROOT / f["path"], ROOT / "runs/d2_data")
            fw, fh = f["width"], f["height"]
            images.append(f'<figure><div class="picture"><img src="{html.escape(rel)}"><svg viewBox="0 0 {fw} {fh}"><rect x="{x0*fw}" y="{y0*fh}" width="{(x1-x0)*fw}" height="{(y1-y0)*fh}"/></svg></div><figcaption>{html.escape(f["frame_id"])} · {sample["pts_s"]:.3f} s · depth pixels {sample["support_depth_points"]}</figcaption></figure>')
        cards.append(f'<article><h2>{html.escape(event["event_id"])} · {event["class_name"]}</h2><p>{event["split"]} / visit {event["visit_id"]} · {event["start_s"]:.3f}–{event["end_s"]:.3f}s · 待独立人工复核</p><div class="samples">{"".join(images)}</div></article>')
    content = '<!doctype html><meta charset="utf-8"><title>方向二事件复核草稿</title><style>body{font:16px system-ui;max-width:1450px;margin:30px auto;color:#18212a}h1{font-size:28px}.notice{padding:16px;background:#fff3cd;line-height:1.6}article{border-top:1px solid #bbb;padding:16px 0}.samples{display:flex;gap:10px}figure{margin:0;flex:1;min-width:0}.picture{position:relative}img{width:100%;display:block}svg{position:absolute;inset:0;width:100%;height:100%}rect{fill:none;stroke:#ff3636;stroke-width:4}figcaption{font-size:12px}h2{font-size:17px}</style><h1>方向二事件复核草稿</h1><div class="notice">这里是公开真实室内影像上的自动家具可见性草稿。框来自已测深度点落在官方三维框内，不是人工逐帧标注。时间是原视频实际 PTS 的 1Hz 采样点；开始不等于“首次足够可判定”，结束有约1秒采样不确定性。所有事件仍待两人独立复核，不能据此报告真实风险召回或质量非劣效。家具保持静止，可见性变化来自相机；没有人为创造的物体状态变化。请在 data/d2/event_review.csv 填写复核记录，并保留分歧。</div>' + ''.join(cards)
    out = ROOT / "runs/d2_data/event_review.html"
    out.write_text(content)
    import csv
    review = ROOT / "data/d2/event_review.csv"
    existing = {}
    if review.exists():
        with review.open() as stream:
            existing = {r["event_id"]: r for r in csv.DictReader(stream)}
    with review.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["event_id", "video_id", "class_name", "proxy_start_s", "proxy_end_s", "reviewer_a", "reviewer_a_start_s", "reviewer_a_end_s", "reviewer_a_class", "reviewer_b", "reviewer_b_start_s", "reviewer_b_end_s", "reviewer_b_class", "adjudicator", "confirmed_start_s", "confirmed_end_s", "first_sufficiently_judgable_s", "critical_category", "status", "notes"])
        writer.writeheader()
        for e in events:
            writer.writerow(existing.get(e["event_id"], {"event_id": e["event_id"], "video_id": e["video_id"], "class_name": e["class_name"], "proxy_start_s": e["start_s"], "proxy_end_s": e["end_s"], "status": "pending"}))


def proxies(video_ids=None):
    statuses = []
    write_json(ROOT / "data/d2/category_map.json", {"mapping": CATEGORY_MAP, "rule": "Frozen before model prediction; unmapped classes including stool are excluded from proxy evaluation"})
    for _, _, vid, _ in VIDEOS:
        if video_ids and vid not in video_ids:
            continue
        status = proxy_one(vid)
        statuses.append(status)
        print(json.dumps(status, ensure_ascii=False), flush=True)
    events, observations = [], []
    for path in sorted((ROOT / "data/d2").glob("proxy_events_*.jsonl")):
        events.extend(json.loads(x) for x in path.read_text().splitlines())
    for path in sorted((ROOT / "data/d2").glob("proxy_observations_*.jsonl")):
        observations.extend(json.loads(x) for x in path.read_text().splitlines())
    write_jsonl(ROOT / "data/d2/proxy_events.jsonl", events)
    write_jsonl(ROOT / "data/d2/proxy_observations.jsonl", observations)
    write_json(ROOT / "runs/d2_data/proxy_status.json", statuses)
    frames = [json.loads(x) for x in (ROOT / "data/d2/frames.jsonl").read_text().splitlines()]
    frame_status = []
    observation_counts = {}
    for observation in observations:
        key = observation["frame_id"]
        observation_counts[key] = observation_counts.get(key, 0) + 1
    video_statuses = {}
    for path in (ROOT / "runs/d2_data").glob("proxy_status_*.json"):
        value = json.loads(path.read_text())
        video_statuses[value["video_id"]] = value
    for frame in frames:
        status = video_statuses.get(frame["video_id"], {})
        skips = {r["frame_id"]: r["reason"] for r in status.get("skipped_frames", [])}
        available = status.get("status") == "proxy_draft" and frame["frame_id"] not in skips
        frame_status.append({"frame_id": frame["frame_id"], "video_id": frame["video_id"], "pts_s": frame["pts_s"], "split": frame["split"], "truth_kind": "derived_visibility", "review_status": "pending", "can_score_confirmed_truth": False, "can_score_proxy": available, "status": "proxy_available" if available else "unavailable", "reason": skips.get(frame["frame_id"], None if available else "Proxy generation unavailable"), "supported_object_count": observation_counts.get(frame["frame_id"], 0)})
    write_jsonl(ROOT / "data/d2/proxy_frame_status.jsonl", frame_status)
    render_review(events, frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["download", "extract", "unpack", "proxy", "orient"])
    parser.add_argument("--videos", nargs="*")
    parser.add_argument("--no-mov", action="store_true")
    parser.add_argument("--no-sparse", action="store_true")
    parser.add_argument("--range-workers", type=int, default=0)
    args = parser.parse_args()
    if args.action == "download":
        download(args.videos, not args.no_mov, not args.no_sparse, args.range_workers)
    elif args.action == "extract":
        extract(args.videos)
    elif args.action == "unpack":
        unpack(args.videos)
    elif args.action == "orient":
        for _, _, vid, _ in VIDEOS:
            if (not args.videos or vid in args.videos) and (ROOT / "data/d2" / f"frames_{vid}.jsonl").exists():
                normalize_orientation(vid)
        rows = []
        for path in sorted((ROOT / "data/d2").glob("frames_*.jsonl")):
            rows.extend(json.loads(x) for x in path.read_text().splitlines())
        write_jsonl(ROOT / "data/d2/frames.jsonl", rows)
    else:
        proxies(args.videos)


if __name__ == "__main__":
    main()
