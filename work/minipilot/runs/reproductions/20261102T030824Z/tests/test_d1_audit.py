"""Source-equivalence, input separation and preserved-run audit tests."""
import ast,json,pathlib,sys,unittest
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pilot'))
import d1_methods as methods
import d1_run as run
from d1_supplement import fixed_matches

class AuditTests(unittest.TestCase):
    def test_snapshot_method_ast_identical_to_original(self):
        source=ROOT.parents[1]/'AnjuGuard/services/backend/app/assessment_service.py'
        if not source.exists():self.skipTest('Original repository optional for portable package')
        def extract(path):
            c=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.ClassDef) and x.name=='AssessmentService')
            return {x.name:ast.dump(x,include_attributes=False) for x in c.body if isinstance(x,ast.FunctionDef) and x.name in ('_merge_cross_frame_candidates','_same_physical_risk')}
        self.assertEqual(extract(source),extract(run.SOURCE))

    def test_adapter_grouping_equivalent_to_source_method(self):
        original=methods.original_class(str(run.SOURCE))()
        rng=np.random.default_rng(25)
        for iteration in range(30):
            frames={f'f{i}':{'frame_id':f'f{i}','source_id':None if iteration%3==0 else 's','captured_at_ms':i*4000 if iteration%2==0 else None,'width':100,'height':100} for i in range(3)}
            obs=[];cs=[]
            for i in range(6):
                fid=f'f{i//2}';x=int(rng.integers(0,40));o={'observation_id':f'o{i}','frame_id':fid,'category':'box','bbox_xyxy':[x,10,x+50,60]};obs.append(o)
                cs.append({'media_id':fid,'risk_code':'box','confidence':1.,'evidence':'publisher bbox','region':{'type':'bbox','x':x/100,'y':.1,'width':.5,'height':.5}})
            source_groups=original._merge_cross_frame_candidates(cs,[{'media_id':fid,**f} for fid,f in frames.items()])
            group_ids=methods.original_groups(obs,frames,run.SOURCE);id_to_frame={o['observation_id']:o['frame_id'] for o in obs}
            self.assertEqual([x['evidence_media_ids'] for x in source_groups],[[id_to_frame[oid] for oid in group] for group in group_ids])

    def test_strict_fix_preserves_missing_source_gate(self):
        left=[{'observation_id':'a','frame_id':'f1','category':'box','bbox_xyxy':[0,0,10,10]}]
        right=[{'observation_id':'b','frame_id':'f2','category':'box','bbox_xyxy':[0,0,10,10]}]
        frames={f:{'frame_id':f,'source_id':None,'sequence_id':'s','captured_at_ms':None} for f in ('f1','f2')}
        self.assertEqual(fixed_matches(left,right,frames),set())
        for f in frames.values():f['source_id']='real-source'
        self.assertEqual(fixed_matches(left,right,frames),{(0,0)})
        self.assertEqual(fixed_matches(left,left,frames),set())

    def test_truth_permutation_cannot_change_real_saved_predictions(self):
        if not (run.RUN/'frozen_config.json').is_file():self.skipTest('Real run not available')
        obs={o['observation_id']:o for o in run.read_jsonl(run.DATA/'algorithm/observations.jsonl')};entries={}
        for value in run.read_jsonl(run.RUN/'frame_pair_outputs.jsonl'):
            entries[(value['left_frame_id'],value['right_frame_id'])]={**value,'left':[obs[x] for x in value['left_observation_ids']],'right':[obs[x] for x in value['right_observation_ids']],'failed':False,**{k:np.array(value[k]) for k in ('similarities','relations','qualities','ious')}}
        frozen=json.loads((run.RUN/'frozen_config.json').read_text());params=frozen['parameters']
        saved={(p['pair_id'],p['method']):p for p in run.read_jsonl(run.RUN/'predictions.jsonl')}
        answers={p['pair_id']:p['same_object'] for p in run.read_jsonl(run.DATA/'evaluation/pairs.jsonl')}
        for q in run.read_jsonl(run.DATA/'algorithm/queries.jsonl'):
            for method in ('A_original','B_frozen','C_relation_quality','C_no_relation','B_binary','C_no_abstention'):
                p=params[method];expected=saved[(q['pair_id'],method)]
                for flip in (False,True):
                    # Poison even extra query fields; implementation must use only allowed observations.
                    adversarial={**q,'same_object':answers[q['pair_id']]^flip,'object_identity':str(flip),'manual_relation':'invented'}
                    actual=run.prediction(adversarial,entries,method,p['dummy_threshold'],p['abstention_margin'],frozen['protocol']['relation_weight'])
                    self.assertEqual(actual['decision'],expected['decision'])
                    # JSON restores geometry float32 values into float64 arrays; allow
                    # serialization roundoff while requiring exactly the same decision.
                    self.assertAlmostEqual(actual['margin'],expected['margin'],delta=1e-7)
                    clean=run.prediction(q,entries,method,p['dummy_threshold'],p['abstention_margin'],frozen['protocol']['relation_weight'])
                    self.assertEqual(actual,clean)

    def test_initial_predictions_unchanged_and_full_supplement(self):
        if not (run.RUN/'supplement_audit.json').exists():self.skipTest('Supplement not run')
        self.assertEqual((run.RUN/'initial_run/per_pair_results.jsonl').read_bytes(),(run.RUN/'per_pair_results.jsonl').read_bytes())
        self.assertEqual((run.RUN/'initial_run/frozen_config.json').read_bytes(),(run.RUN/'frozen_config.json').read_bytes())
        rows=run.read_jsonl(run.RUN/'all_8_methods_per_pair.jsonl');self.assertEqual(len(rows),384)
        self.assertEqual(sum(r['method']=='A_fix' for r in rows),48)

if __name__=='__main__':unittest.main()
