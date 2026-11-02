"""Re-evaluate recorded outputs only. Cached reads are never inference timings."""
import collections
import datetime
import json
from pathlib import Path
import d1_run
import d2

ROOT=Path(__file__).resolve().parents[1]


def require_complete(rows, expected_ids, key):
    actual=[r[key] for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected_ids):
        raise ValueError(f'Incomplete or duplicate results for {key}: expected {len(expected_ids)}, got {len(actual)}')


def main():
    target=ROOT/'runs/recomputed'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target.mkdir(parents=True,exist_ok=False)
    pairs=d1_run.read_jsonl(ROOT/'data/d1/evaluation/pairs.jsonl')
    truth={r['pair_id']:r for r in pairs}
    rows=d1_run.read_jsonl(ROOT/'runs/d1/all_8_methods_per_pair.jsonl')
    expected_methods=set(d1_run.METHODS)|{'A_fix'}
    if {r['method'] for r in rows} != expected_methods: raise ValueError('Missing D1 method')
    for method in expected_methods:
        require_complete([r for r in rows if r['method']==method],truth,'pair_id')
    for r in rows:
        r['same_object']=truth[r['pair_id']]['same_object']
        r['stratum']=truth[r['pair_id']]['stratum']
        r['outcome']=r['decision'] if r['decision'] in ('failed','pending') else ('correct' if (r['decision']=='same')==r['same_object'] else 'error')
    d1_run.METHODS=tuple(sorted(expected_methods))
    summary=d1_run.summarize(rows)
    (target/'d1').mkdir();d1_run.dump(target/'d1/summary.json',summary);d1_run.csv_write(target/'d1/summary.csv',summary)
    for split in ('dev','test'):
        base=ROOT/'runs/d2'/split
        events=d2.read_jsonl(base/'input_events.jsonl');frames=d2.read_jsonl(base/'input_frames.jsonl')
        paths=list(base.glob('*/config.json'))
        if split=='test' and {p.parent.name for p in paths} != {'A_fixed','B_original','C_fix','C_tuned','D_candidate'}:
            raise ValueError('Missing D2 test policy')
        if not paths: raise ValueError('Missing D2 outputs')
        result=[]
        for config_path in sorted(paths):
            folder=config_path.parent
            decisions=d2.read_jsonl(folder/'decisions.jsonl');requests=d2.read_jsonl(folder/'requests.jsonl')
            require_complete(decisions,[r['frame_id'] for r in frames],'frame_id')
            cfg=json.loads(config_path.read_text());out=target/'d2'/split/folder.name;out.mkdir(parents=True)
            summary=d2.evaluate(events,decisions,requests,out,policy_config=cfg)
            summary['run_mode']='recomputed_from_recorded_predictions_no_new_inference'
            result.append({'policy':folder.name,**summary})
        d2.write_jsonl(target/'d2'/split/'summary.jsonl',result)
        d2.export_summary_csv(target/'d2'/split/'summary.csv',result)
    (target/'mode.json').write_text(json.dumps({'kind':'evaluation_recomputation','new_model_calls':0,
        'latency_source':'original recorded HTTP timings, never cache read speed','complete':True},indent=2))
    print(target)


if __name__=='__main__':main()
