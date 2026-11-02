"""Synthetic implementation tests; these are not real-data research results."""
import copy, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pilot'))
import d1_methods as m
import d1_run as run

class AssociationTests(unittest.TestCase):
    def test_iou(self):
        self.assertEqual(m.iou([0,0,10,10],[0,0,10,10]),1)
        self.assertEqual(m.iou([0,0,10,10],[20,20,30,30]),0)
        self.assertEqual(m.iou([0,0,0,0],[0,0,0,0]),0)

    def test_unmatched_dummies(self):
        self.assertEqual(m.assignment(np.array([[.1,.2],[.3,.4]]),.5),set())
        self.assertEqual(m.assignment(np.array([[.8,.2],[.75,.1]]),.5),{(0,0)})

    def test_one_to_one_global_assignment(self):
        result=m.assignment(np.array([[.9,.8],[.89,.1]]),.2)
        self.assertEqual(result,{(0,1),(1,0)})
        self.assertEqual(len({i for i,j in result}),len(result))
        self.assertEqual(len({j for i,j in result}),len(result))

    def test_empty_and_equal_threshold(self):
        self.assertEqual(m.assignment(np.empty((0,2)),.5),set())
        self.assertEqual(m.assignment(np.array([[.5]]),.5),set())

    def test_pending_boundary_and_conflict_margin(self):
        self.assertEqual(m.decide(.1,.1),'same')
        self.assertEqual(m.decide(-.1,.1),'different')
        self.assertEqual(m.decide(.09,.1),'pending')
        scores=np.array([[.9,.89],[.8,.4]])
        pairs=m.assignment(scores,.5)
        self.assertLess(m.pair_margin(scores,pairs,1,1,.5),0)

    def test_original_documented_behaviors(self):
        cls=m.original_class(str(run.SOURCE));obj=cls()
        def c(fid):return {'media_id':fid,'risk_code':'box','confidence':1.,'evidence':fid,'region':{'type':'bbox','x':.1,'y':.1,'width':.3,'height':.3}}
        self.assertEqual(len(obj._merge_cross_frame_candidates([c('a'),c('b')],[{'media_id':'a','source_id':'a'},{'media_id':'b','source_id':'b'}])),2)
        self.assertEqual(len(obj._merge_cross_frame_candidates([c('a'),c('b')],[{'media_id':'a','source_id':'s'},{'media_id':'b','source_id':'s'}])),1)
        self.assertEqual(obj._merge_cross_frame_candidates([c('a'),c('a')],[{'media_id':'a','source_id':'s'}])[0]['evidence_media_ids'],['a','a'])
        self.assertEqual(len(obj._merge_cross_frame_candidates([c('a'),c('b')],[{'media_id':'a','source_id':'s','captured_at_ms':1000},{'media_id':'b','source_id':'s','captured_at_ms':10000}])),2)

    def test_quality_blank_and_good(self):
        blank=m.quality(Image.fromarray(np.zeros((20,20,3),np.uint8)))
        noise=m.quality(Image.fromarray(np.random.default_rng(1).integers(0,255,(128,128,3),dtype=np.uint8)))
        self.assertLess(blank['quality'],noise['quality'])
        self.assertGreater(blank['quality'],0)

    def test_geometry_blank_is_unavailable(self):
        a=Image.fromarray(np.zeros((240,320,3),np.uint8))
        h,meta=m.geometry(a,a,[],[])
        self.assertIsNone(h);self.assertFalse(meta['valid'])
        left=[{'bbox_xyxy':[1,1,10,10]}]
        self.assertEqual(float(m.relation_scores(h,left,left,400)[0,0]),.5)

    def test_geometry_known_translation(self):
        a=np.random.default_rng(2).integers(0,255,(320,400,3),dtype=np.uint8)
        import cv2
        b=cv2.warpAffine(a,np.float32([[1,0,10],[0,1,7]]),(400,320))
        h,meta=m.geometry(Image.fromarray(a),Image.fromarray(b),[],[])
        self.assertTrue(meta['valid'],meta)
        self.assertAlmostEqual(h[0,2],10,delta=2);self.assertAlmostEqual(h[1,2],7,delta=2)

    def fixture(self):
        q={'pair_id':'p','left_frame_id':'a','right_frame_id':'b','left_observation_id':'a0','right_observation_id':'b0','split':'development'}
        entry={'left':[{'observation_id':'a0'}],'right':[{'observation_id':'b0'}],'similarities':np.array([[.8]]),'relations':np.array([[.5]]),'qualities':np.array([[.7]]),'ious':np.array([[.8]]),'original_groups':[['a0'],['b0']],'geometry':{'valid':False},'failed':False}
        return q,{('a','b'):entry}

    def test_prediction_ignores_truth_fields(self):
        q,entries=self.fixture();normal=run.prediction(q,entries,'B_frozen',.5,.1,.15)
        poisoned={**q,'same_object':False,'object_identity':'fake','manual_relation':'left'}
        self.assertEqual(normal,run.prediction(poisoned,entries,'B_frozen',.5,.1,.15))

    def test_missing_feature_is_failed_not_negative(self):
        q,entries=self.fixture();entries[('a','b')]={'failed':True,'missing':['a0']}
        self.assertEqual(run.prediction(q,entries,'B_frozen',.5,.1,.15)['decision'],'failed')

    def test_summary_preserves_pending_and_failures(self):
        rows=[]
        for same,decision in [(True,'pending'),(False,'same'),(True,'failed'),(True,'different')]:
            rows.append({'method':'B_frozen','split':'development','same_object':same,'decision':decision,'stratum':'same_instance' if same else 'same_category_different_instance','decision_seconds':0.})
        row=next(x for x in run.summarize(rows) if x['method']=='B_frozen' and x['split']=='development')
        self.assertEqual(row['result_completeness'],.75);self.assertEqual(row['automatic_fraction'],.5)
        self.assertEqual(row['decided_error_rate'],1);self.assertEqual(row['pending'],1);self.assertEqual(row['failed'],1)

    def test_algorithm_files_do_not_contain_identity_answers(self):
        forbidden={'same_object','object_identity','publisher_instance','manual_relation','problem_id'}
        for path in (ROOT/'data/d1/algorithm').glob('*.jsonl'):
            for line in path.read_text().splitlines():self.assertTrue(forbidden.isdisjoint(json.loads(line)),path)

    def test_every_result_and_configuration_exists(self):
        if not (run.RUN/'per_pair_results.jsonl').is_file():self.skipTest('Run artifacts not created')
        rows=run.read_jsonl(run.RUN/'per_pair_results.jsonl');self.assertEqual(len(rows),48*7)
        self.assertEqual(set(r['method'] for r in rows),set(run.METHODS))
        for pair in {r['pair_id'] for r in rows}:self.assertEqual(sum(r['pair_id']==pair for r in rows),7)
        self.assertEqual((run.RUN/'frozen_config.sha256').read_text().strip(),run.sha256(run.RUN/'frozen_config.json'))
        self.assertTrue(all(r['decision'] in ('same','different','pending','failed') for r in rows))

if __name__=='__main__':unittest.main()
