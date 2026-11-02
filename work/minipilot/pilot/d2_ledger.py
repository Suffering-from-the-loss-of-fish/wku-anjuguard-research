"""Reconcile fresh client calls against the preserved server journal."""
from __future__ import annotations

import json
from pathlib import Path

from d2 import ROOT, read_jsonl


def main() -> None:
    server = read_jsonl(ROOT / "runs/model_server/requests.jsonl")
    # Probe repeats deliberately have some of the same logical request IDs.
    # The server start timestamp and image digest disambiguate physical calls.
    def key(row: dict) -> tuple:
        return row.get("request_id"), row.get("started_utc"), row.get("image_sha256")
    index = {key(row): row for row in server}
    out = {"server_rows": len(server), "groups": {}, "total_missing_server_records": 0}
    for group in ("dev", "test", "independent_http_probe"):
        calls = [r for path in (ROOT / "runs/d2" / group).glob("*/requests.jsonl")
                 for r in read_jsonl(path) if r["execution_mode"] == "real_http"]
        missing = [r["request_id"] for r in calls if key(r["response"]) not in index]
        status_mismatches = [r["request_id"] for r in calls if key(r["response"]) in index
                             and r["response"].get("status") != index[key(r["response"])].get("status")]
        out["groups"][group] = {"fresh_real_calls": len(calls),
            "http_attempts": sum(len(r["attempts"]) for r in calls),
            "matched_server_records": len(calls) - len(missing),
            "missing_server_request_ids": missing, "status_mismatch_request_ids": status_mismatches,
            "paid_api_cost": sum(r.get("api_cost", 0) for r in calls),
            "timeout_or_transport_errors": sum(any(a.get("error") for a in r["attempts"]) for r in calls)}
        out["total_missing_server_records"] += len(missing)
    out["warning"] = "Paid API cost excludes electricity and equipment; no money-savings estimate. Unrelated warmups and old technical probes are outside these groups."
    (ROOT / "runs/d2/server_ledger.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
