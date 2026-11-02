"""Prepare a deterministic RGB-only, publisher-annotated identity pilot."""
from __future__ import annotations
import hashlib, io, json, pathlib, random, re, tarfile
import numpy as np
from PIL import Image
from scipy.io import loadmat
from d1_download import ROOT, SCENES, sha256

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))

def annotations(value):
    if isinstance(value,dict): yield value
    elif getattr(value,'_fieldnames',None): yield {k:getattr(value,k) for k in value._fieldnames}
    elif isinstance(value,(list,np.ndarray)):
        for x in value: yield from annotations(x)

def main():
    data=ROOT/'data/d1'; frames=[];observations=[];labels=[];pairs=[];scene_stats=[]
    for scene in SCENES:
        split='development' if scene in SCENES[:2] else 'exploratory_holdout'
        with tarfile.open(data/'raw'/f'{scene}.tar','r:*') as archive:
            names=archive.getnames()
            images=sorted((n for n in names if n.endswith('.png') and not n.endswith('_depth.png')),key=lambda n:int(re.search(r'_(\d+)\.png$',n).group(1)))
            mat_name=next(n for n in names if n.endswith('.mat'))
            raw_mat=archive.extractfile(mat_name).read()
            bboxes=loadmat(io.BytesIO(raw_mat),simplify_cells=True)['bboxes']
            indices=np.linspace(0,len(images)-1,16).round().astype(int)
            scene_obs=[]
            for pos in indices:
                member=images[int(pos)]; frame_number=int(re.search(r'_(\d+)\.png$',member).group(1))
                assert 1<=frame_number<=len(bboxes), (scene,frame_number,len(bboxes))
                fid=f'{scene}_f{frame_number:04d}'; rel=pathlib.Path('data/d1/images')/scene/(fid+'.png')
                out=ROOT/rel;out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(archive.extractfile(member).read())
                with Image.open(out) as im: width,height=im.size;im.verify()
                frames.append({'frame_id':fid,'image_path':str(rel),'sha256':sha256(out),'sequence_id':scene,'split':split,'source_frame_index':frame_number,'captured_at_ms':None,'source_id':None,'width':width,'height':height,'source_archive_member':member})
                raw_anns=list(annotations(bboxes[frame_number-1]))
                for ordinal,ann in enumerate(raw_anns):
                    # Published MATLAB rectangles use one-based inclusive corners.
                    x0=max(0,int(ann['left'])-1);y0=max(0,int(ann['top'])-1)
                    x1=min(width,int(ann['right']));y1=min(height,int(ann['bottom']))
                    if x1<=x0 or y1<=y0: raise ValueError(f'Invalid bbox in {fid}: {ann}')
                    oid=f'{fid}_o{ordinal:02d}'
                    item={'observation_id':oid,'frame_id':fid,'category':str(ann['category']),'bbox_xyxy':[x0,y0,x1,y1],'candidate_source':'publisher_projected_annotation','candidate_review_status':'independent_human_review_pending'}
                    observations.append(item);scene_obs.append(item)
                    labels.append({'observation_id':oid,'object_identity':f"{ann['category']}:{int(ann['instance'])}",'publisher_category':str(ann['category']),'publisher_instance':int(ann['instance']),'source':'UW RGB-D Scenes v1','independent_human_review_status':'pending'})
            label_map={x['observation_id']:x['object_identity'] for x in labels}
            pos_pool=[];neg_hard=[];neg_easy=[]
            for i,a in enumerate(scene_obs):
                for b in scene_obs[i+1:]:
                    if a['frame_id']==b['frame_id']:continue
                    record={'left_observation_id':a['observation_id'],'right_observation_id':b['observation_id'],'left_frame_id':a['frame_id'],'right_frame_id':b['frame_id']}
                    if label_map[a['observation_id']]==label_map[b['observation_id']]:pos_pool.append(record)
                    elif a['category']==b['category']:neg_hard.append(record)
                    else:neg_easy.append(record)
            rng=random.Random('anju-d1-fixed-pairs-20261101:'+scene)
            for pool in (pos_pool,neg_hard,neg_easy):rng.shuffle(pool)
            chosen=[(x,True,'same_instance') for x in pos_pool[:6]]
            negatives=[(x,False,'same_category_different_instance') for x in neg_hard[:6]]
            negatives += [(x,False,'different_category_easy') for x in neg_easy[:6-len(negatives)]]
            chosen+=negatives
            for ordinal,(item,same,stratum) in enumerate(chosen):
                pairs.append({'pair_id':f'{scene}_p{ordinal+1:02d}', 'sequence_id':scene,'split':split,**item,'same_object':same,'stratum':stratum,'independent_human_review_status':'pending'})
            scene_stats.append({'sequence_id':scene,'split':split,'rgb_frames_in_archive':len(images),'selected_frames':len(indices),'observations':len(scene_obs),'selected_same_pairs':sum(x[1] for x in chosen),'selected_different_pairs':sum(not x[1] for x in chosen),'same_category_negative_pool':len(neg_hard),'selected_same_category_negatives':len([x for x in negatives if x[2]=='same_category_different_instance']),'scene_group_independence':'unverified'})
    write_jsonl(data/'algorithm/frames.jsonl',frames)
    write_jsonl(data/'algorithm/observations.jsonl',observations)
    write_jsonl(data/'evaluation/labels.jsonl',labels)
    write_jsonl(data/'evaluation/pairs.jsonl',pairs)
    # Public query IDs contain no answers or instance identifiers.
    write_jsonl(data/'algorithm/queries.jsonl',[{k:p[k] for k in ('pair_id','left_observation_id','right_observation_id','left_frame_id','right_frame_id','split')} for p in pairs])
    manifest={'dataset':'UW RGB-D Scenes v1','evidence_type':'real_public_rgb_images_publisher_labels_not_independently_reverified','scene_groups_are_not_verified_independent_sites':True,'timestamp_status':'not provided; no FPS-derived timestamps fabricated','bbox_conversion':'MATLAB one-based inclusive -> Python zero-based half-open; pending human review','sampling':'16 rounded equally spaced available frame positions per sequence, no model-based selection','pair_sampling':'seeded before feature inference; six same and six different per sequence; same-category negatives preferred','split_policy':'desk_1,kitchen_small_1 development; meeting_small_1,table_1 exploratory holdout; site independence unknown','scenes':scene_stats,'algorithm_files':{},'evaluation_files':{}}
    for part in ('algorithm','evaluation'):
        manifest[part+'_files']={str(p.relative_to(ROOT)):sha256(p) for p in sorted((data/part).glob('*.jsonl'))}
    (data/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
