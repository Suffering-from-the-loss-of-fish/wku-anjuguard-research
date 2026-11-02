"""Add an original-metadata engineering baseline without changing first-run B/C outputs."""
from __future__ import annotations
import json, pathlib, time
import numpy as np
import d1_run as run
from d1_methods import assignment, iou, original_class

def fixed_matches(left,right,frames):
    if not left or not right:return set()
    lf,rf=frames[left[0]['frame_id']],frames[right[0]['frame_id']]
    # Preserve the original source and time gates; never substitute sequence IDs here.
    if lf['frame_id']==rf['frame_id'] or not lf.get('source_id') or lf.get('source_id')!=rf.get('source_id'):return set()
    lt,rt=lf.get('captured_at_ms'),rf.get('captured_at_ms')
    if isinstance(lt,int) and isinstance(rt,int) and abs(lt-rt)>8000:return set()
    scores=np.array([[iou(a['bbox_xyxy'],b['bbox_xyxy']) if a['category']==b['category'] else -1 for b in right] for a in left])
    return assignment(scores,np.nextafter(.35,-np.inf))

def main():
    root=run.ROOT;out=run.RUN
    frames={x['frame_id']:x for x in run.read_jsonl(run.DATA/'algorithm/frames.jsonl')}
    observations=run.read_jsonl(run.DATA/'algorithm/observations.jsonl');byframe={fid:[o for o in observations if o['frame_id']==fid] for fid in frames}
    queries=run.read_jsonl(run.DATA/'algorithm/queries.jsonl');truth={x['pair_id']:x for x in run.read_jsonl(run.DATA/'evaluation/pairs.jsonl')}
    new=[]
    for q in queries:
        left,right=byframe[q['left_frame_id']],byframe[q['right_frame_id']];t=time.perf_counter()
        matches=fixed_matches(left,right,frames)
        li=next(i for i,x in enumerate(left) if x['observation_id']==q['left_observation_id']);ri=next(i for i,x in enumerate(right) if x['observation_id']==q['right_observation_id'])
        same=(li,ri) in matches;elapsed=time.perf_counter()-t;gt=truth[q['pair_id']]
        new.append({**q,'method':'A_fix','decision':'same' if same else 'different','margin':1. if same else -1.,'reason':'original_source_gate_plus_same_frame_exclusion_and_one_to_one_IoU','geometry_valid':False,'decision_seconds':elapsed,'same_object':gt['same_object'],'stratum':gt['stratum'],'outcome':'correct' if same==gt['same_object'] else 'error','human_review_status':'pending','evidence_status':'publisher_labels_initial_measurement'})
    original=run.read_jsonl(out/'per_pair_results.jsonl');combined=original+new
    run.write_jsonl(out/'supplement_A_fix.jsonl',new);run.csv_write(out/'supplement_A_fix.csv',new)
    run.write_jsonl(out/'all_8_methods_per_pair.jsonl',combined);run.csv_write(out/'all_8_methods_per_pair.csv',combined)
    methods=run.METHODS;run.METHODS=methods[:1]+('A_fix',)+methods[1:]
    summary=run.summarize(combined);run.METHODS=methods
    run.dump(out/'all_8_methods_summary.json',summary);run.csv_write(out/'all_8_methods_summary.csv',summary)
    run.csv_write(out/'all_8_methods_coverage.csv',[{k:r[k] for k in ('split','method','pairs','automatic_count','automatic_fraction','decided_errors','decided_error_rate','pending','failed','result_completeness')} for r in summary])
    # Preserve the first run's case file, emit updated eight-method review separately.
    old_html=(out/'review_cases.html').read_bytes();run.create_html(combined,frames,observations)
    (out/'all_8_methods_review.html').write_bytes((out/'review_cases.html').read_bytes());(out/'review_cases.html').write_bytes(old_html)
    first=run.read_jsonl(out/'frame_pair_outputs.jsonl');timing=json.loads((out/'run_log.json').read_text());features=timing['feature_timing']
    performance={'evidence_type':'recorded_real_local_pipeline_wall_times','initial_integrated_wall_seconds':timing['elapsed_seconds'],'feature_extraction_wall_including_model_load_crops_quality_preprocessing_forward_and_save_seconds':features['feature_extraction_wall_seconds'],'model_load_seconds':features['encoder_load_seconds'],'encoder_forward_seconds':features['encoder_forward_seconds'],'encoder_preprocessing_seconds':features['preprocessing_seconds'],'frame_pair_shared_geometry_matching_preparation_seconds':sum(x['compute_seconds'] for x in first),'all_7_methods_decision_total_seconds':sum(x['decision_seconds'] for x in original),'supplement_A_fix_decision_total_seconds':sum(x['decision_seconds'] for x in new),'quality_only_seconds':None,'quality_timing_note':'Included in feature_extraction_wall; not separately instrumented in initial run. Do not infer isolated quality runtime by subtracting unrelated timing terms.','per_method_complete_pipeline_latency_comparison':'not measured independently; feature/geometry preparation shared','api_calls':0,'api_charge_usd':0,'electricity_cost_and_device_energy':'not measured','cached_speed_is_inference_latency':False}
    run.dump(out/'performance_accounting.json',performance)
    audit={'type':'supplemental engineering and portability audit after initial holdout results','initial_run_preserved_in':'initial_run/','initial_predictions_sha256':run.sha256(out/'per_pair_results.jsonl'),'initial_frozen_config_sha256':run.sha256(out/'frozen_config.json'),'new_method':'A_fix','source_metadata_unchanged':True,'B_C_parameters_or_predictions_changed':False,'new_baseline_file_sha256':run.sha256(root/'pilot/d1_baseline_source.py'),'current_code_sha256':{str(p.relative_to(root)):run.sha256(p) for p in sorted((root/'pilot').glob('d1*.py'))},'snapshot_provenance':'AnjuGuard df281277215a1b55fd74dc8e43203e3954081976; only two method bodies copied unchanged','limitations':'supplement is audit, not new holdout tuning; all research results remain exploratory'}
    run.dump(out/'supplement_audit.json',audit)
    print(json.dumps({'added_rows':len(new),'total_rows':len(combined),'timing':performance},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
