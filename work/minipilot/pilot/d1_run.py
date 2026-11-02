"""Execute frozen-feature association, development calibration, holdout prediction and evaluation."""
from __future__ import annotations
import argparse, collections, csv, hashlib, html, json, math, os, pathlib, time
import numpy as np
from PIL import Image
from d1_download import ROOT, sha256
from d1_data import write_jsonl
from d1_methods import assignment, decide, geometry, iou, original_groups, pair_margin, quality, relation_scores

METHODS=('A_original','A_fix_sequence_adapter','B_frozen','C_relation_quality','C_no_relation','C_no_abstention','B_binary')
# Portable, source-equivalent snapshot. Original repository is not needed at runtime.
SOURCE=pathlib.Path(__file__).with_name('d1_baseline_source.py')
DATA=ROOT/'data/d1'; RUN=pathlib.Path(os.environ.get('D1_RUN_DIR',str(ROOT/'runs/d1'))).resolve()

def read_jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def extract_features(observations,frames,config):
    import torch
    from transformers import AutoImageProcessor, AutoModel
    torch.set_num_threads(config['torch_threads']);torch.manual_seed(config['random_seed'])
    torch.use_deterministic_algorithms(True)
    start=time.perf_counter();model_path=ROOT/'models/dinov2-small'
    processor=AutoImageProcessor.from_pretrained(str(model_path),local_files_only=True,use_fast=False)
    model=AutoModel.from_pretrained(str(model_path),local_files_only=True).to('cpu').eval()
    load_s=time.perf_counter()-start
    images={fid:Image.open(ROOT/f['image_path']).convert('RGB') for fid,f in frames.items()}
    crops=[images[o['frame_id']].crop(o['bbox_xyxy']) for o in observations]
    qualities={o['observation_id']:quality(c) for o,c in zip(observations,crops)}
    features={};failures=[];batches=[]
    for offset in range(0,len(crops),config['batch_size']):
        batch_crops=crops[offset:offset+config['batch_size']];batch_obs=observations[offset:offset+config['batch_size']]
        t=time.perf_counter()
        try:
            inputs=processor(images=batch_crops,return_tensors='pt');preprocess_s=time.perf_counter()-t;t_infer=time.perf_counter()
            with torch.inference_mode():output=model(**inputs).last_hidden_state[:,0,:]
            embeddings=torch.nn.functional.normalize(output,dim=-1).cpu().numpy()
            infer_s=time.perf_counter()-t_infer
            for o,embedding in zip(batch_obs,embeddings):features[o['observation_id']]=embedding
            batches.append({'offset':offset,'count':len(batch_obs),'preprocess_seconds':preprocess_s,'inference_seconds':infer_s,'status':'completed'})
        except Exception as exc:
            for o in batch_obs:failures.append({'observation_id':o['observation_id'],'error':repr(exc),'stage':'real_encoder_inference'})
            batches.append({'offset':offset,'count':len(batch_obs),'status':'failed','elapsed_seconds':time.perf_counter()-t,'error':repr(exc)})
        print(json.dumps({'stage':'features','completed':min(offset+len(batch_obs),len(crops)),'total':len(crops),'failures':len(failures)}),flush=True)
    np.savez_compressed(RUN/'features.npz',observation_ids=np.array(list(features)),embeddings=np.array(list(features.values())))
    write_jsonl(RUN/'quality.jsonl',[{'observation_id':oid,**q} for oid,q in qualities.items()])
    write_jsonl(RUN/'feature_failures.jsonl',failures)
    timing={'evidence_type':'real_local_frozen_neural_model_inference','device':'cpu','dtype':'float32','torch_threads':config['torch_threads'],'encoder_load_seconds':load_s,'feature_extraction_wall_seconds':time.perf_counter()-start,'encoder_forward_seconds':sum(b.get('inference_seconds',0) for b in batches),'preprocessing_seconds':sum(b.get('preprocess_seconds',0) for b in batches),'successful_observations':len(features),'failed_observations':len(failures),'batches':batches,'api_calls':0,'api_charge_usd':0,'electricity_cost':'not measured','cache_used':False}
    dump(RUN/'feature_timing.json',timing)
    return features,qualities,images,timing

def build_frame_pairs(queries,observations,frames,features,qualities,images):
    byframe=collections.defaultdict(list)
    for o in observations:byframe[o['frame_id']].append(o)
    outputs={};logs=[]
    for query in queries:
        key=(query['left_frame_id'],query['right_frame_id'])
        if key in outputs:continue
        left,right=byframe[key[0]],byframe[key[1]];start=time.perf_counter()
        missing=[o['observation_id'] for o in left+right if o['observation_id'] not in features]
        if missing:outputs[key]={'failed':True,'missing':missing};continue
        left_vec=np.stack([features[o['observation_id']] for o in left]);right_vec=np.stack([features[o['observation_id']] for o in right])
        sims=np.clip(left_vec@right_vec.T,-1,1).astype(float)
        for i,a in enumerate(left):
            for j,b in enumerate(right):
                if a['category']!=b['category']:sims[i,j]=-1.
        h,geo=geometry(images[key[0]],images[key[1]],[o['bbox_xyxy'] for o in left],[o['bbox_xyxy'] for o in right])
        rel=relation_scores(h,left,right,math.hypot(frames[key[1]]['width'],frames[key[1]]['height']))
        q=np.array([[min(qualities[a['observation_id']]['quality'],qualities[b['observation_id']]['quality']) for b in right] for a in left])
        ious=np.array([[iou(a['bbox_xyxy'],b['bbox_xyxy']) if a['category']==b['category'] else -1. for b in right] for a in left])
        groups=original_groups(left+right,frames,SOURCE)
        item={'left':left,'right':right,'similarities':sims,'relations':rel,'qualities':q,'ious':ious,'geometry':geo,'original_groups':groups,'failed':False,'compute_seconds':time.perf_counter()-start}
        outputs[key]=item
        logs.append({'left_frame_id':key[0],'right_frame_id':key[1],'geometry':geo,'compute_seconds':item['compute_seconds'],'similarities':sims.tolist(),'relations':rel.tolist(),'qualities':q.tolist(),'ious':ious.tolist(),'left_observation_ids':[o['observation_id'] for o in left],'right_observation_ids':[o['observation_id'] for o in right],'original_groups':groups})
    write_jsonl(RUN/'frame_pair_outputs.jsonl',logs)
    return outputs

def prediction(query,frame_pairs,method,threshold,abstention,relation_weight):
    entry=frame_pairs[(query['left_frame_id'],query['right_frame_id'])]
    if entry.get('failed'):return {'decision':'failed','margin':None,'reason':'feature_failure','geometry_valid':False}
    li={o['observation_id']:i for i,o in enumerate(entry['left'])};ri={o['observation_id']:i for i,o in enumerate(entry['right'])}
    i,j=li[query['left_observation_id']],ri[query['right_observation_id']]
    if method=='A_original':
        same=any(query['left_observation_id'] in g and query['right_observation_id'] in g for g in entry['original_groups'])
        return {'decision':'same' if same else 'different','margin':1. if same else -1.,'reason':'exact_original_rule_with_current_photo_source_metadata','geometry_valid':entry['geometry']['valid']}
    if method=='A_fix_sequence_adapter':
        matches=assignment(entry['ious'],.35);same=(i,j) in matches
        return {'decision':'same' if same else 'different','margin':1. if same else -1.,'reason':'public_sequence_id_input_adapter_plus_one_to_one_IoU_time_unavailable','geometry_valid':entry['geometry']['valid']}
    scores=entry['similarities'].copy()
    if method in ('C_relation_quality','C_no_abstention'):
        valid=scores>=0;scores[valid]=np.clip(scores[valid]+relation_weight*(entry['relations'][valid]-.5),0,1)
    matches=assignment(scores,threshold);margin=pair_margin(scores,matches,i,j,threshold)
    if method in ('C_relation_quality','C_no_relation','C_no_abstention') and scores[i,j]>=0:margin*=entry['qualities'][i,j]
    decision=decide(margin,abstention)
    return {'decision':decision,'margin':float(margin),'reason':'one_to_one_with_dummy_and_development_calibrated_margin','geometry_valid':entry['geometry']['valid']}

def calibrate(dev_queries,dev_labels,frame_pairs,config):
    parameters={};search=[]
    for method in ('B_frozen','C_relation_quality','C_no_relation'):
        options=[]
        for threshold in config['dummy_threshold_grid']:
            preds=[prediction(q,frame_pairs,method,threshold,0,config['relation_weight']) for q in dev_queries]
            valid=[(q,p) for q,p in zip(dev_queries,preds) if p['decision']!='failed']
            errors=sum((p['decision']=='same')!=dev_labels[q['pair_id']] for q,p in valid)
            options.append((errors,abs(threshold-.65),threshold,preds))
            search.append({'method':method,'dummy_threshold':threshold,'development_binary_errors':errors,'development_total':len(dev_queries)})
        errors,_,threshold,preds=min(options,key=lambda x:(x[0],x[1],x[2]))
        margins=sorted(abs(p['margin']) for p in preds if p['margin'] is not None)
        count=min(len(margins),math.ceil(len(dev_queries)*config['automatic_decision_target']))
        abstention=margins[-count] if count else float('inf')
        parameters[method]={'dummy_threshold':threshold,'abstention_margin':abstention,'development_binary_errors':errors,'automatic_target':config['automatic_decision_target'],'development_automatic_count':sum(m+1e-12>=abstention for m in margins),'development_pairs':len(dev_queries)}
    parameters['B_binary']={**parameters['B_frozen'],'abstention_margin':0.}
    parameters['C_no_abstention']={**parameters['C_relation_quality'],'abstention_margin':0.}
    parameters['A_original']={'dummy_threshold':0.,'abstention_margin':0.}
    parameters['A_fix_sequence_adapter']={'dummy_threshold':.35,'abstention_margin':0.}
    write_jsonl(RUN/'development_search.jsonl',search)
    return parameters

def summarize(rows):
    output=[]
    for split in ('development','exploratory_holdout','all'):
        for method in METHODS:
            values=[r for r in rows if r['method']==method and (split=='all' or r['split']==split)]
            n=len(values);same=sum(r['same_object'] for r in values);different=n-same
            auto=[r for r in values if r['decision'] in ('same','different')]
            fm=sum(r['decision']=='same' and not r['same_object'] for r in values)
            fn=sum(r['decision']=='different' and r['same_object'] for r in values)
            pending=sum(r['decision']=='pending' for r in values);failed=sum(r['decision']=='failed' for r in values)
            hard=[r for r in values if r['stratum']=='same_category_different_instance']
            output.append({'split':split,'method':method,'pairs':n,'same_pairs':same,'different_pairs':different,'false_merges':fm,'missed_merges':fn,'pending':pending,'failed':failed,'complete_count':n-failed,'result_completeness':(n-failed)/n if n else None,'automatic_count':len(auto),'automatic_fraction':len(auto)/n if n else None,'decided_errors':fm+fn,'decided_error_rate':(fm+fn)/len(auto) if auto else None,'false_merge_rate_all_negative_pairs':fm/different if different else None,'missed_merge_rate_all_positive_pairs':fn/same if same else None,'same_category_negative_pairs':len(hard),'false_merges_same_category':sum(r['decision']=='same' for r in hard),'decision_seconds':sum(r['decision_seconds'] for r in values)})
    return output

def create_html(rows,frames,observations):
    obs={x['observation_id']:x for x in observations}
    bypair=collections.defaultdict(list)
    for row in rows:bypair[row['pair_id']].append(row)
    def picture(oid):
        o=obs[oid];f=frames[o['frame_id']];x0,y0,x1,y1=o['bbox_xyxy'];path=os.path.relpath(ROOT/f['image_path'],RUN)
        return f'<figure><svg viewBox="0 0 {f["width"]} {f["height"]}" role="img"><image href="{html.escape(path)}" width="{f["width"]}" height="{f["height"]}"/><rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="#ff3355" stroke-width="4"/></svg><figcaption>{html.escape(oid)} · {html.escape(o["category"])} · 原帧 {f["source_frame_index"]}</figcaption></figure>'
    chunks=['<!doctype html><meta charset="utf-8"><title>方向一预实验逐对复核与失败案例</title><style>body{font:16px/1.6 system-ui;max-width:1240px;margin:30px auto;padding:0 20px;color:#17212b}article{border-top:1px solid #ccc;padding:24px 0}.images{display:flex;gap:16px}figure{width:49%;margin:0}svg{width:100%;background:#eee}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ccc;padding:6px;text-align:left}.bad{background:#fee}.pending{background:#fff7df}summary{cursor:pointer}small{color:#555}</style><h1>方向一预实验逐对复核与失败案例</h1><p>真实公开 RGB 图片与发布方标注初测。尚未完成本轮独立人工复核；序列不是已验证的独立场地。红框是统一输入候选框。先看图片作判断，再展开发布方答案与算法结果。</p>']
    ordered=sorted(bypair.items(),key=lambda item:(not any(r['outcome'] in ('error','failed','pending') for r in item[1]),item[0]))
    for pair_id,values in ordered:
        r=values[0];chunks.append(f'<article id="{pair_id}"><h2>{pair_id} · {r["split"]}</h2><div class="images">{picture(r["left_observation_id"])}{picture(r["right_observation_id"])}</div><details><summary>发布方答案与算法结果（用于复核，不是新增人工确认）</summary><p>发布方答案：{"同一实物" if r["same_object"] else "不同实物"}；配对类别：{r["stratum"]}</p><table><tr><th>方法</th><th>决定</th><th>状态</th><th>决策余量</th><th>自动参照可用</th></tr>')
        for v in values:chunks.append(f'<tr class="{"bad" if v["outcome"] in ("error","failed") else "pending" if v["outcome"]=="pending" else ""}"><td>{v["method"]}</td><td>{v["decision"]}</td><td>{v["outcome"]}</td><td>{v["margin"]}</td><td>{v["geometry_valid"]}</td></tr>')
        chunks.append('</table></details></article>')
    (RUN/'review_cases.html').write_text(''.join(chunks))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reuse-features',action='store_true');args=parser.parse_args()
    RUN.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    config=json.loads((ROOT/'configs/d1_protocol.json').read_text())
    frames={f['frame_id']:f for f in read_jsonl(DATA/'algorithm/frames.jsonl')};observations=read_jsonl(DATA/'algorithm/observations.jsonl');queries=read_jsonl(DATA/'algorithm/queries.jsonl')
    if args.reuse_features:
        loaded=np.load(RUN/'features.npz');features=dict(zip(loaded['observation_ids'],loaded['embeddings']))
        qualities={x['observation_id']:x for x in read_jsonl(RUN/'quality.jsonl')};images={fid:Image.open(ROOT/f['image_path']).convert('RGB') for fid,f in frames.items()}
        timing=json.loads((RUN/'feature_timing.json').read_text());timing['cache_used_for_this_run']=True
    else:features,qualities,images,timing=extract_features(observations,frames,config)
    frame_pairs=build_frame_pairs(queries,observations,frames,features,qualities,images)
    # Only development answers are passed to calibration. The predictor receives none.
    dev_queries=[q for q in queries if q['split']=='development']
    dev_labels={p['pair_id']:p['same_object'] for p in read_jsonl(DATA/'evaluation/pairs.jsonl') if p['split']=='development'}
    parameters=calibrate(dev_queries,dev_labels,frame_pairs,config)
    frozen={'protocol':config,'parameters':parameters,'source_sha256':sha256(SOURCE),'data_manifest_sha256':sha256(DATA/'manifest.json'),'pair_list_sha256':sha256(DATA/'evaluation/pairs.jsonl'),'model_files_sha256':{p.name:sha256(p) for p in sorted((ROOT/'models/dinov2-small').glob('*')) if p.is_file()},'code_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'pilot').glob('d1*.py'))},'freeze_stage':'after development calibration, before holdout prediction/evaluation','holdout_labels_used_for_parameter_selection':False}
    dump(RUN/'frozen_config.json',frozen)
    (RUN/'frozen_config.sha256').write_text(sha256(RUN/'frozen_config.json')+'\n')
    predictions=[]
    for query in queries:
        for method in METHODS:
            p=parameters[method];t=time.perf_counter();pred=prediction(query,frame_pairs,method,p['dummy_threshold'],p['abstention_margin'],config['relation_weight'])
            predictions.append({**query,'method':method,**pred,'decision_seconds':time.perf_counter()-t})
    write_jsonl(RUN/'predictions.jsonl',predictions)
    # Holdout answers are joined only after all predictions and configuration are saved.
    evaluation={p['pair_id']:p for p in read_jsonl(DATA/'evaluation/pairs.jsonl')}
    rows=[]
    for pred in predictions:
        truth=evaluation[pred['pair_id']];decision=pred['decision']
        outcome=decision if decision in ('pending','failed') else 'correct' if (decision=='same')==truth['same_object'] else 'error'
        rows.append({**pred,'same_object':truth['same_object'],'stratum':truth['stratum'],'outcome':outcome,'human_review_status':'pending','evidence_status':'publisher_labels_initial_measurement'})
    write_jsonl(RUN/'per_pair_results.jsonl',rows);csv_write(RUN/'per_pair_results.csv',rows)
    summary=summarize(rows);csv_write(RUN/'summary.csv',summary);dump(RUN/'summary.json',summary)
    csv_write(RUN/'coverage.csv',[{k:r[k] for k in ('split','method','pairs','automatic_count','automatic_fraction','decided_errors','decided_error_rate','pending','failed','result_completeness')} for r in summary])
    create_html(rows,frames,observations)
    runlog={'status':'completed','evidence_status':'real_public_rgb_with_real_local_dinov2_inference_and_publisher_annotations_initial_measurement','independent_human_review':'not completed','strict_site_holdout':'not verified','api_calls':0,'api_charge_usd':0,'electricity_or_device_energy':'not measured','elapsed_seconds':time.perf_counter()-start,'feature_timing':timing,'geometry_valid_frame_pairs':sum(e['geometry']['valid'] for e in frame_pairs.values() if not e.get('failed')),'unique_frame_pairs':len(frame_pairs),'candidate_observations':len(observations),'selected_images':len(frames),'fixed_evaluation_pairs':len(queries),'frozen_config_sha256':sha256(RUN/'frozen_config.json'),'source_commit':'df281277215a1b55fd74dc8e43203e3954081976','limitations':['desk negative pairs are different-category easy negatives','same physical publisher instances may appear across sequences','published RGB frame timestamps unavailable','bounding boxes have not undergone new independent human review','automatic background homography is only approximate planar evidence, not 3-D truth']}
    dump(RUN/'run_log.json',runlog)
    print(json.dumps({'summary':[s for s in summary if s['split']=='exploratory_holdout'],'run_log':runlog},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
