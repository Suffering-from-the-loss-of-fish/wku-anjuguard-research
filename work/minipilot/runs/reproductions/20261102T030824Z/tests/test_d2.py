import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("d2", ROOT/"pilot/d2.py")
d2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = d2
spec.loader.exec_module(d2)


def feat(hash_value="0000000000000000"):
    return {"brightness":120,"sharpness":20,"hash":hash_value,"small":np.zeros((96,128),dtype=np.float32)}


def response(usable=True):
    return {"status":"ok","result":{"quality_usable":usable,"objects":[]}}


def test_original_quality_rejection_poisoning_preserved_and_fixed():
    original=d2.Policy("B","original")
    fixed=d2.Policy("C","fixed_gate")
    for policy in (original,fixed):
        policy.sent(0)
        policy.returned(1,0,feat(),response(False))
    assert original.submitted_hash == feat()["hash"]
    assert fixed.submitted_hash is None
    assert original.decide(6,feat(),False)[1] == "duplicate"
    assert fixed.decide(6,feat(),False)[0] == "low"


def test_original_cap_and_failure_backoff():
    policy=d2.Policy("B","original")
    policy.requests=30
    assert policy.decide(1000,feat(),False)[1] == "request_cap"
    policy.requests=0
    policy.returned(1,0,feat(),{"status":"error"})
    assert policy.next_allowed == 5
    assert policy.decide(4,feat(),False)[1] == "cooldown"
    assert policy.decide(5,feat(),False)[0] == "low"


def test_dhash_blind_spot_and_tile_signal():
    w,h=720,540
    y,x=np.indices((h,w))
    gray=np.where((x//12+y//12)%2,150,100).astype(np.uint8)
    first=Image.fromarray(np.repeat(gray[:,:,None],3,axis=2))
    changed=np.array(first)
    changed[10:30,15:45]=20
    a,b=d2.features(first),d2.features(Image.fromarray(changed))
    assert d2.hamming(a["hash"],b["hash"]) == 0
    assert b["sharpness"] >= 5
    assert d2.local_change(b["small"],a["small"]) > 0


def test_d_local_change_and_expiry():
    policy=d2.Policy("D","candidate",local_threshold=.1,result_ttl_s=12)
    f=feat()
    policy.sent(0);policy.returned(1,0,f,response())
    changed=feat();changed["small"][0:12,0:16]=.5
    assert policy.decide(7,changed,False)[:2] == ("high","local_change")
    assert policy.decide(14,f,False)[0] == "high"


def test_future_response_invisible_during_pending(tmp_path, monkeypatch):
    path=tmp_path/"image.jpg"
    Image.new("RGB",(80,60),(120,120,120)).save(path)
    frames=[{"frame_id":f"f{i}","video_id":"v","visit_id":"site","split":"dev","pts_s":i,"path":str(path),"duration_s":5} for i in range(5)]
    class Client:
        def call(self,path,rid):
            return {"request_id":rid,"response":response(),"effective_latency_s":2.1,"execution_mode":"real_http","attempts":[],"image_bytes":100}
    monkeypatch.setattr(d2,"ROOT",tmp_path)
    decisions,requests=d2.run_policy(frames,{"name":"A","kind":"fixed","interval_s":1},Client(),tmp_path/"out")
    assert decisions[1]["reason"] == "inflight"
    assert decisions[2]["visible_result_times_s"] == []
    assert decisions[3]["visible_result_times_s"][0] > 2
    assert all(t <= r["pts_s"] for r in decisions for t in r["visible_result_times_s"])


def test_failed_and_unfinished_requests_retained(tmp_path, monkeypatch):
    path=tmp_path/"image.jpg";Image.new("RGB",(20,20)).save(path)
    frame={"frame_id":"f","video_id":"v","split":"dev","pts_s":0,"path":str(path),"duration_s":1}
    class Client:
        def call(self,path,rid):
            return {"request_id":rid,"response":{"status":"error","error":"timeout"},"effective_latency_s":5,"execution_mode":"real_http","attempts":[{"http_latency_s":5,"http_request_body_bytes":10}],"image_bytes":100}
    monkeypatch.setattr(d2,"ROOT",tmp_path)
    decisions,requests=d2.run_policy([frame],{"name":"A","kind":"fixed"},Client(),tmp_path/"out")
    summary=d2.evaluate([],decisions,requests,tmp_path/"out")
    assert summary["unfinished_at_video_end"] == 1
    assert summary["request_status_counts"]["error"] == 1
    assert summary["logical_attempts_including_replays"] == 1
    assert summary["human_reviewed_event_metrics"] == "未测"


def test_late_event_never_counts_as_timely(tmp_path):
    event={"event_id":"e","video_id":"v","class_name":"chair","start_s":0,"end_s":2,"frames":[{"frame_id":"f","bbox":[0,0,1,1]}],"truth_kind":"derived_visibility","review_status":"pending"}
    req={"request_id":"r","video_id":"v","frame_id":"f","response":{"status":"ok","result":{"quality_usable":True,"objects":[{"category":"chair","bbox":[0,0,1,1]}]}},"source_pts_s":0,"completed_at_s":3,"execution_mode":"recorded_response","attempts":[],"image_bytes":100,"status_at_video_end":"unfinished"}
    summary=d2.evaluate([event],[],[req],tmp_path)
    assert summary["proxy_recall_by_deadline"]["20"] == 0
    assert summary["proxy_late_after_visibility_end"] == 1
    assert summary["new_real_http_requests"] == 0


def test_cache_uses_recorded_latency_and_no_http(tmp_path,monkeypatch):
    image=tmp_path/"image.jpg";image.write_bytes(b"synthetic")
    client=d2.HTTPModel("http://127.0.0.1:9",tmp_path/"cache",{"model_id":"fixed"})
    key=d2.digest({"image_sha256":d2.digest(b"synthetic"),"model_contract":{"model_id":"fixed"},"timeout_s":120,"max_retries":1})
    (tmp_path/"cache"/f"{key}.json").write_text(json.dumps({"request_id":"old","effective_latency_s":7,"response":response(),"attempts":[]}))
    def fail(*a,**k):raise AssertionError("must not call network")
    monkeypatch.setattr(d2.urllib.request,"urlopen",fail)
    out=client.call(image,"new")
    assert out["effective_latency_s"] == 7
    assert out["execution_mode"] == "recorded_response"


def test_annotations_never_passed_to_policy():
    # The runtime entry point consumes frames/config/client only. Event truth is
    # an evaluation-only argument, loaded after independent model responses.
    import inspect
    assert "events" not in inspect.signature(d2.run_policy).parameters
    assert "event" not in inspect.getsource(d2.Policy.decide)


def test_timeout_is_logged_and_not_duplicated(tmp_path,monkeypatch):
    image=tmp_path/"image.jpg";image.write_bytes(b"synthetic")
    client=d2.HTTPModel("http://127.0.0.1:9",tmp_path/"cache",{},timeout_s=.1)
    calls=[]
    def timeout(*a,**k):
        calls.append(1)
        raise TimeoutError("synthetic timeout")
    monkeypatch.setattr(d2.urllib.request,"urlopen",timeout)
    out=client.call(image,"r")
    assert len(calls) == 1
    assert out["response"]["status"] == "error"
    assert len(out["attempts"]) == 1
    assert "TimeoutError" in out["attempts"][0]["error"]


def test_http_retry_is_bounded_and_cost_kept(tmp_path,monkeypatch):
    import io
    image=tmp_path/"image.jpg";image.write_bytes(b"synthetic")
    client=d2.HTTPModel("http://127.0.0.1:9",tmp_path/"cache",{},max_retries=1)
    def unavailable(*a,**k):
        raise d2.urllib.error.HTTPError("local",503,"busy",{},io.BytesIO(b"busy"))
    monkeypatch.setattr(d2.urllib.request,"urlopen",unavailable)
    monkeypatch.setattr(d2.time,"sleep",lambda _:None)
    out=client.call(image,"r")
    assert len(out["attempts"]) == 2
    assert sum(a["http_request_body_bytes"] for a in out["attempts"]) > 0


def test_expiry_cannot_hide_loss_of_answer_coverage(tmp_path):
    event={"event_id":"e","video_id":"v","class_name":"chair","start_s":0,"end_s":2,"frames":[{"frame_id":"f","bbox":[0,0,1,1]}]}
    req={"request_id":"r","video_id":"v","frame_id":"f","response":{"status":"ok","result":{"quality_usable":True,"objects":[{"category":"chair","bbox":[0,0,1,1]}]}},"source_pts_s":0,"completed_at_s":1,"execution_mode":"recorded_response","attempts":[],"image_bytes":100,"status_at_video_end":"completed"}
    decision={"frame_id":"later","video_id":"v","pts_s":5,"scheduler_compute_ms":0,"reason":"wait"}
    base=d2.evaluate([event],[decision],[req],tmp_path)
    candidate=d2.evaluate([event],[decision],[req],tmp_path,policy_config={"kind":"candidate","result_ttl_s":3})
    assert base["proxy_stale_answer_ticks"] == 1
    assert candidate["proxy_stale_answer_ticks"] == 0
    assert candidate["answer_coverage"] == 0


def test_split_cannot_leak_same_acquisition_group():
    import pytest
    frames=[{"frame_id":"a","video_id":"v1","visit_id":"same","split":"dev","pts_s":0,"duration_s":10},{"frame_id":"b","video_id":"v2","visit_id":"same","split":"test","pts_s":0,"duration_s":10}]
    with pytest.raises(ValueError,match="crosses"):
        d2.validate_manifest(frames)
