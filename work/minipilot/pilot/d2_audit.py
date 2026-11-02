"""Read completed outputs and add reference-availability and causal audits.

This never selects parameters and does not change d2.py or frozen results.
Unmatched proxy boxes are not independently confirmed false positives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def audit(split: str) -> dict:
    statuses={r["frame_id"]:r for r in rows(ROOT/"data/d2/proxy_frame_status.jsonl")}
    folder=ROOT/"runs/d2"/split
    result={"split":split,"policies":{},"error_count":0}
    for path in sorted(folder.glob("*/summary.json")):
        method=path.parent
        decisions,requests,events=rows(method/"decisions.jsonl"),rows(method/"requests.jsonl"),rows(method/"events.jsonl")
        violations=[]
        for d in decisions:
            if any(t>d["pts_s"] for t in d["visible_result_times_s"]):
                violations.append({"frame_id":d["frame_id"],"error":"future_response_exposed"})
        for r in requests:
            if r["completed_at_s"]<r["source_pts_s"]:
                violations.append({"request_id":r["request_id"],"error":"negative_latency"})
            if len(r["attempts"])>2:
                violations.append({"request_id":r["request_id"],"error":"retry_limit_exceeded"})
        event_match_count={}
        for e in events:
            for m in e["matching_outputs"]:
                event_match_count[m["request_id"]]=event_match_count.get(m["request_id"],0)+1
        scorable_objects=unscorable_objects=scorable_unmatched=0
        valid_requests=unscorable_requests=0
        for req in requests:
            if req["response"].get("status")!="ok":
                continue
            objects=(req["response"].get("result") or {}).get("objects",[])
            valid_requests+=1
            if not statuses.get(req["frame_id"],{}).get("can_score_proxy",False):
                unscorable_objects+=len(objects);unscorable_requests+=1
            else:
                scorable_objects+=len(objects)
                scorable_unmatched+=len(objects)-event_match_count.get(req["request_id"],0)
        scorable_ticks=sum(bool(statuses.get(d["frame_id"],{}).get("can_score_proxy",False)) for d in decisions)
        supplemental={"frames_with_proxy_reference":scorable_ticks,"all_frames":len(decisions),"proxy_reference_completeness":scorable_ticks/len(decisions) if decisions else None,"valid_responses_without_proxy_reference":unscorable_requests,"predicted_objects_without_proxy_reference":unscorable_objects,"predicted_objects_with_proxy_reference":scorable_objects,"unmatched_predictions_on_scorable_proxy_frames":scorable_unmatched,"confirmed_false_positive_rate":None,"confirmed_truth_coverage":0,"interpretation":"未匹配代理框不是人工确认误报；无参考帧单列，不按空场景判断。", "causal_and_retry_violations":violations}
        (method/"reference_audit.json").write_text(json.dumps(supplemental,ensure_ascii=False,indent=2))
        result["policies"][method.name]=supplemental
        result["error_count"]+=len(violations)
    freeze=ROOT/"configs/d2_frozen.json"
    if freeze.exists():
        frozen=json.loads(freeze.read_text())
        result["frozen_code_matches"]=hashlib.sha256((ROOT/"pilot/d2.py").read_bytes()).hexdigest()==frozen["code_sha256"]
        manifest=folder/"run_manifest.json"
        if split=="test" and manifest.exists():
            result["test_started_after_freeze"]=json.loads(manifest.read_text())["started_unix_s"]>=frozen["created_unix_s"]
    (folder/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--split",choices=["dev","test"],required=True)
    value=audit(p.parse_args().split)
    print(json.dumps({"policies":len(value["policies"]),"error_count":value["error_count"],"frozen_code_matches":value.get("frozen_code_matches"),"test_started_after_freeze":value.get("test_started_after_freeze")},ensure_ascii=False))
