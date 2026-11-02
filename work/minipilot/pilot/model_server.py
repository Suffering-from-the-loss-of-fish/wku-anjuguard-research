"""Fixed, stateless local VLM over HTTP; never calls a paid endpoint.

Start: .venv/bin/python -m pilot.model_server
Each call performs inference again, without cross-request response/KV/vision cache.
The process binds only 127.0.0.1. Raw outputs are appended even if a client times out.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"
REVISION = "46d4cf06a06ffc1a766c214174f9cbed2f45bcab"
CATEGORIES = ("chair", "table", "sofa", "cabinet", "bed", "shelf")
PROMPT = '''Inspect only the single supplied image. Detect visible indoor furniture from exactly these categories: chair, table, sofa, cabinet, bed, shelf. A desk is table; a couch is sofa; a bookcase is shelf. Do not infer hidden objects or use prior images. Return all visibly identifiable instances of those categories. For a partly occluded object, bound only its visible image extent. If the picture is too dark, blurred or otherwise unusable for judging furniture, set quality_usable to false. Return ONLY a JSON object, with no markdown or explanation, in this format:
{"quality_usable":true,"objects":[{"category":"chair","bbox":[100,200,300,400]}]}
Each bbox is [left,top,right,bottom] in PIXELS of the supplied image, with origin at the image top-left. Use left<right and top<bottom. The exact supplied image width and height follow. If no listed furniture is visibly identifiable, return an empty objects array. Do not report risk, safety, object identities or probabilities.'''
PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()


def parse_output(text: str, width: int = 1000, height: int = 1000) -> dict:
    """Strictly validate; markdown fence removal is the only text normalization."""
    s = text.strip()
    if s.startswith("```") and s.endswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(s)
    if not isinstance(result, dict) or type(result.get("quality_usable")) is not bool:
        raise ValueError("quality_usable must be a boolean")
    if not isinstance(result.get("objects"), list):
        raise ValueError("objects must be a list")
    out = []
    for obj in result["objects"]:
        if not isinstance(obj, dict) or obj.get("category") not in CATEGORIES:
            raise ValueError("unknown category")
        box = obj.get("bbox")
        if not isinstance(box, list) or len(box) != 4 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            or v < 0 for v in box
        ):
            raise ValueError("invalid bbox coordinates")
        if box[0] > width or box[2] > width or box[1] > height or box[3] > height:
            raise ValueError("bbox exceeds supplied image dimensions")
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("invalid bbox extent")
        out.append({"category": obj["category"], "bbox": [box[0]/width, box[1]/height, box[2]/width, box[3]/height]})
    return {"quality_usable": result["quality_usable"], "objects": out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/qwen2.5-vl-3b-4bit")
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import uvicorn
    import mlx.core as mx
    from mlx_vlm import load, generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from mlx_vlm.structured import build_json_schema_logits_processor
    from PIL import Image

    # Loading from the pinned local snapshot never downloads a different revision.
    load_start = time.perf_counter()
    model, processor = load(str(args.model_dir), trust_remote_code=False)
    config = load_config(str(args.model_dir))
    formatted = apply_chat_template(processor, config, PROMPT, num_images=1)
    load_s = time.perf_counter() - load_start
    busy = threading.Lock()
    logdir = ROOT / "runs/model_server"
    logdir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model_id": MODEL_ID, "model_revision": REVISION, "prompt": PROMPT,
        "prompt_sha256": PROMPT_SHA, "formatted_prompt_sha256": hashlib.sha256(formatted.encode()).hexdigest(),
        "temperature": 0.0, "max_tokens": args.max_tokens, "model_load_seconds": load_s,
        "cross_request_cache": False, "api_cost": 0, "cost_scope": "local_API_fee_only",
        "experiment_kind": "real_local_model_http", "categories": list(CATEGORIES),
        "structured_decoding": "JSON schema; per-request fresh grammar; no truth input",
        "bbox_units_model": "supplied_image_pixels", "bbox_units_response": "normalized_0_1",
        "decoding_version": "json_schema_unbounded_integers_then_strict_pixel_validation_v2",
        "server_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    (logdir / "server_config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    app = FastAPI(title="AnjuGuard minimum pilot fixed local model")

    class AnalyzeRequest(BaseModel):
        image_path: str | None = None
        image_base64: str | None = None
        mime_type: str = "image/jpeg"
        request_id: str

    @app.get("/health")
    def health():
        return {"status": "ready", "busy": busy.locked(), **metadata}

    @app.post("/analyze")
    def analyze(body: AnalyzeRequest):
        if body.image_base64 is not None:
            if len(body.image_base64) > 16_000_000 or body.mime_type not in ("image/jpeg", "image/png"):
                raise HTTPException(400, "image payload too large or unsupported mime type")
            try:
                content = base64.b64decode(body.image_base64, validate=True)
            except ValueError:
                raise HTTPException(400, "invalid base64")
            received = logdir / "received_images"
            received.mkdir(exist_ok=True)
            suffix = ".jpg" if body.mime_type == "image/jpeg" else ".png"
            path = received / (hashlib.sha256(content).hexdigest() + suffix)
            if not path.exists():
                path.write_bytes(content)
        elif body.image_path:
            path = Path(body.image_path).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise HTTPException(400, "image must exist under experiment directory")
        else:
            raise HTTPException(400, "image_base64 or image_path is required")
        if not busy.acquire(blocking=False):
            raise HTTPException(429, "single inference worker busy")
        start = time.perf_counter()
        record = {"request_id": body.request_id, "image_path": str(path),
                  "model_id": MODEL_ID, "model_revision": REVISION, "prompt_sha256": PROMPT_SHA,
                  "decoding_version": metadata["decoding_version"], "server_code_sha256": metadata["server_code_sha256"],
                  "started_utc": datetime.now(timezone.utc).isoformat(),
                  "experiment_kind": "real_local_model_http", "api_cost": 0,
                  "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "image_bytes": path.stat().st_size, "cache_hit": False}
        try:
            with Image.open(path) as im:
                width, height = im.size
            actual_prompt = PROMPT + f"\nImage width: {width} pixels. Image height: {height} pixels."
            actual_formatted = apply_chat_template(processor, config, actual_prompt, num_images=1)
            record["actual_prompt_sha256"] = hashlib.sha256(actual_formatted.encode()).hexdigest()
            schema = {"type":"object","properties":{
                "quality_usable":{"type":"boolean"},
                "objects":{"type":"array","items":{"type":"object","properties":{
                    "category":{"type":"string","enum":list(CATEGORIES)},
                    "bbox":{"type":"array","items":{"type":"integer"},"minItems":4,"maxItems":4}},
                    "required":["category","bbox"],"additionalProperties":False}}},
                "required":["quality_usable","objects"],"additionalProperties":False}
            tokenizer = processor.tokenizer if hasattr(processor,"tokenizer") else processor
            grammar = build_json_schema_logits_processor(tokenizer, schema)
            mx.random.seed(0)
            generation = generate(model, processor, actual_formatted, image=[str(path)],
                                  max_tokens=args.max_tokens, temperature=0.0, verbose=False,
                                  logits_processors=[grammar])
            mx.synchronize()
            record["raw_text"] = generation.text
            record["usage"] = {k: getattr(generation, k, None) for k in
                               ("prompt_tokens", "generation_tokens", "total_tokens", "cached_tokens")}
            record["finish_reason"] = str(getattr(generation, "finish_reason", "unknown"))
            record["peak_memory_gb"] = getattr(generation, "peak_memory", None)
            try:
                record["result"] = parse_output(generation.text, width, height)
                record["status"] = "ok"
            except (ValueError, TypeError, KeyError) as exc:
                record.update(status="invalid", result=None, error=str(exc))
        except Exception as exc:
            record.update(status="error", result=None, raw_text=record.get("raw_text", ""),
                          error=f"{type(exc).__name__}: {exc}")
        finally:
            record["latency_ms"] = (time.perf_counter() - start) * 1000
            record["finished_utc"] = datetime.now(timezone.utc).isoformat()
            with (logdir / "requests.jsonl").open("a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            mx.clear_cache()
            busy.release()
        return record

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
