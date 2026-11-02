"""Build a local review index from real recorded outputs; no human labels invented."""
from pathlib import Path
import html
import json
ROOT=Path(__file__).resolve().parents[1]

def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def esc(x):return html.escape(str(x))
def uri(p):return (ROOT/p).resolve().as_uri()
def main():
    frames={x['frame_id']:x for x in rows(ROOT/'data/d1/algorithm/frames.jsonl')}
    obs={x['observation_id']:x for x in rows(ROOT/'data/d1/algorithm/observations.jsonl')}
    d1=rows(ROOT/'runs/d1/all_8_methods_per_pair.jsonl')
    chunks=['<!DOCTYPE html><html lang="zh"><meta charset="utf-8"><title>AnjuGuard 失败与待复核案例</title><style>body{font:16px/1.65 system-ui;max-width:1160px;margin:32px auto;padding:0 18px;color:#17212b}article{border-top:1px solid #bbb;padding:20px 0}.pair{display:flex;gap:14px}figure{margin:0;flex:1}svg,img{max-width:100%;max-height:440px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f6;padding:12px}a{color:#154d82}td,th{border:1px solid #ccc;padding:7px}table{border-collapse:collapse;width:100%}.note{color:#624619}</style><body><h1>AnjuGuard 失败与待复核案例</h1><p>真实公开图像、真实本机模型输出。独立人工复核为零。方向一按发布方身份标签评价；方向二仅派生可见性参考，不是人工确认的风险漏报。</p>']
    chunks.append(f'<p><a href="{uri(Path("runs/d1/all_8_methods_review.html"))}">全部 48 对身份复核</a> · <a href="{uri(Path("runs/d2_data/event_review.html"))}">全部 250 段事件复核</a></p><h2>方向一 留出中的错误与待确认</h2>')
    selected=sorted({r['pair_id'] for r in d1 if r['split']=='exploratory_holdout' and r['method'] in ('B_frozen','C_relation_quality') and r['outcome'] in ('error','pending','failed')})
    for pid in selected:
        values=[r for r in d1 if r['pair_id']==pid];row=values[0]
        chunks.append(f'<article id="{pid}"><h3>{pid}</h3><div class="pair">')
        for k in ('left_observation_id','right_observation_id'):
            o=obs[row[k]];f=frames[o['frame_id']];x,y,x2,y2=o['bbox_xyxy']
            chunks.append(f'<figure><svg viewBox="0 0 {f["width"]} {f["height"]}"><image href="{uri(Path(f["image_path"]))}" width="{f["width"]}" height="{f["height"]}"/><rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" stroke="#ed3e45" stroke-width="4" fill="none"/></svg><figcaption>{esc(row[k])} 原帧 {f["source_frame_index"]}</figcaption></figure>')
        chunks.append('</div><details><summary>展开发布方答案和算法结果</summary>')
        chunks.append(f'<p>发布方：{"同一实物" if row["same_object"] else "不同实物"}；仍待双人核验。</p><table><tr><th>方法</th><th>判定</th><th>状态</th><th>原因</th></tr>')
        for r in values:chunks.append(f'<tr><td>{r["method"]}</td><td>{r["decision"]}</td><td>{r["outcome"]}</td><td>{esc(r["reason"])}</td></tr>')
        chunks.append('</table></details></article>')
    chunks.append('<h2>方向二 全部留出运行失败与未完成</h2><p class="note">以下无效框或截止视频结束仍未返回是实际执行问题。代理未匹配事件另列，不能直接叫作真实误报/漏报。</p>')
    allframes={x['frame_id']:x for x in rows(ROOT/'data/d2/frames.jsonl')}
    n=0
    for method in ('A_fixed','B_original','C_fix','C_tuned','D_candidate'):
        requests=rows(ROOT/f'runs/d2/test/{method}/requests.jsonl')
        for r in requests:
            if r['response'].get('status')=='ok' and r['status_at_video_end']!='unfinished':continue
            n+=1;f=allframes[r['frame_id']]
            chunks.append(f'<article id="{esc(r["request_id"])}"><h3>{esc(r["request_id"])}</h3><p>视频 {f["video_id"]} · 原始 PTS {f["source_pts_s"]:.6f} 秒 · {esc(r["response"].get("status"))} · {r["status_at_video_end"]}</p><img src="{uri(Path(f["path"]))}" alt="对应实际输入帧"><p><a href="{uri(Path(f["source_video"]))}#t={f["source_pts_s"]:.6f}">原视频对应时刻</a> · <a href="{uri(Path(r["image_path"]))}">实际编码上传图</a></p><p>{esc(r["response"].get("error","视频结束时请求仍在途"))}</p><pre>{esc(r["response"].get("raw_text",""))}</pre></article>')
        cases=rows(ROOT/f'runs/d2/test/{method}/failure_cases.jsonl')
        proxy=[x for x in cases if x['case_type'].startswith('proxy_')]
        chunks.append(f'<details><summary>{method} 的 {len(proxy)} 个派生参考未匹配或晚到事件</summary>')
        for c in proxy:
            chunks.append(f'<p><a href="{uri(Path(c["image_path"]))}">{esc(c["event_id"])} · PTS {c["source_pts_s"]:.3f}s</a> · {esc(c["class_name"])} · {esc(c["case_type"])} · 待人工复核</p>')
        chunks.append('</details>')
    chunks.append('<h2>使用与检查范围</h2><p>本文件通过静态 HTML 解析和本地图片存在/可解码检查。浏览器工具拒绝 file 协议，所以未声称已完成浏览器交互视觉检查。文件链接指向本轮工作区；解压到新位置后运行 python pilot/build_failures.py 可重建。原始视频在代码包中不重复打包，下载器可恢复。</p></body></html>')
    out=ROOT/'delivery/失败案例.html';out.parent.mkdir(exist_ok=True);out.write_text(''.join(chunks))
    print(json.dumps({'path':str(out),'direction1_pairs':len(selected),'direction2_failed_or_unfinished_requests':n},ensure_ascii=False))

if __name__=='__main__':main()
