"""Recompute all d2 metrics from saved chronological decisions and raw outputs.

No model, HTTP, response cache lookup, tuning, or alteration of original results.
Use d2.py for a fresh strategy/model run; this command reproduces the reported
evaluation of the recorded experiment exactly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from d2 import ROOT, evaluate, export_cases, export_summary_csv, read_jsonl, write_jsonl


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--split",choices=["dev","test"],required=True)
    args=p.parse_args()
    source=ROOT/"runs/d2"/args.split
    destination=ROOT/"runs/d2/reanalyzed"/args.split
    frames,events=read_jsonl(source/"input_frames.jsonl"),read_jsonl(source/"input_events.jsonl")
    summaries=[];checks=[]
    for method in sorted(source.glob("*/config.json")):
        folder=method.parent;out=destination/folder.name;out.mkdir(parents=True,exist_ok=True)
        decisions,requests=read_jsonl(folder/"decisions.jsonl"),read_jsonl(folder/"requests.jsonl")
        config=json.loads(method.read_text())
        summary=evaluate(events,decisions,requests,out,policy_config=config)
        original=json.loads((folder/"summary.json").read_text())
        for key in ("run_mode","max_frames_debug_limit"):
            if key in original:summary[key]=original[key]
        equal=summary==original
        checks.append({"policy":folder.name,"exact_summary_reproduced":equal,"different_fields":[k for k in set(summary)|set(original) if summary.get(k)!=original.get(k)]})
        export_cases(frames,read_jsonl(out/"events.jsonl"),requests,out)
        (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        summaries.append({"policy":folder.name,**summary})
    write_jsonl(destination/"summary.jsonl",summaries);export_summary_csv(destination/"summary.csv",summaries)
    write_jsonl(destination/"verification.jsonl",checks)
    print(json.dumps({"split":args.split,"policies":len(checks),"exact_reproduction":all(c["exact_summary_reproduced"] for c in checks)},ensure_ascii=False))
    if not checks or not all(c["exact_summary_reproduced"] for c in checks):
        raise SystemExit(1)


if __name__=="__main__":main()
