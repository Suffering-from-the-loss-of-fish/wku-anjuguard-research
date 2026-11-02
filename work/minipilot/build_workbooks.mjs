import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const QA=path.join(ROOT,'runs/artifact_qa/sheets');
const OUT=path.join(ROOT,'delivery');
const FONT='Arial';
const colors={ink:'#182738',navy:'#243C55',blue:'#EAF0F6',amber:'#FFF2CC',line:'#D8E0E7',red:'#FBE7E7',muted:'#546575'};
const policies=['A_fixed','B_original','C_fix','C_tuned','D_candidate'];
const d1methods=['A_original','A_fix','A_fix_sequence_adapter','B_frozen','C_relation_quality','C_no_relation','C_no_abstention','B_binary'];
const methodNames={A_original:'原规则',A_fix:'原元数据工程修复',A_fix_sequence_adapter:'公开序列适配 辅助',B_frozen:'冻结特征与待确认',C_relation_quality:'关系加质量与待确认',C_no_relation:'去掉关系',C_no_abstention:'C取消待确认',B_binary:'B取消待确认',A_fixed:'固定间隔',B_original:'原质量与哈希',C_fix:'修复简单规则',C_tuned:'开发集调优规则',D_candidate:'局部变化及过期检查'};
const json=async p=>JSON.parse(await fs.readFile(path.join(ROOT,p),'utf8'));
const lines=async p=>(await fs.readFile(path.join(ROOT,p),'utf8')).split(/\r?\n/).filter(Boolean).map(x=>JSON.parse(x));
const col=n=>{let s='';for(let k=n+1;k;k=Math.floor((k-1)/26))s=String.fromCharCode(65+(k-1)%26)+s;return s;};
const linkTarget=p=>pathToFileURL(path.isAbsolute(p)?p:path.join(ROOT,p)).href;
const empty=v=>v===undefined||v===null?'未测':v;
const rowStart=6;

function base(wb,name,title,widths,rows=30){
  const s=wb.worksheets.add(name);s.showGridLines=false;
  s.getRange(`A1:${col(widths.length-1)}${rows}`).format={font:{name:FONT,size:10,color:colors.ink},rowHeight:23,verticalAlignment:'center'};
  widths.forEach((w,i)=>s.getRange(`${col(i)}1:${col(i)}${rows}`).format.columnWidthPx=w);
  s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:FONT,size:14,bold:true,color:colors.ink};s.getRange(`A2:${col(widths.length-1)}2`).format.rowHeight=29;
  return s;
}
function table(s,headers,rows,at=5,name){
  const end=col(headers.length-1),bottom=at+rows.length;
  s.getRange(`A${at}:${end}${bottom}`).values=[headers,...rows];
  s.getRange(`A${at}:${end}${at}`).format={fill:colors.navy,font:{name:FONT,size:10,bold:true,color:'#FFFFFF'},rowHeight:34,horizontalAlignment:'center',verticalAlignment:'center',wrapText:true};
  for(let r=at+1;r<=bottom;r++)if((r-at)%2===0)s.getRange(`A${r}:${end}${r}`).format.fill='#F3F6F9';
  s.getRange(`A${bottom}:${end}${bottom}`).format.borders={bottom:{style:'thin',color:colors.line}};
  if(name&&rows.length){const t=s.tables.add(`A${at}:${end}${bottom}`,true,name);t.showFilterButton=true;}
  return {start:at+1,end:bottom};
}
function note(s,row,text,end='L'){s.getRange(`A${row}`).values=[[text]];s.getRange(`A${row}:${end}${row}`).format={font:{name:FONT,size:10,color:colors.muted},rowHeight:25};}
function fmt(s,range,format){s.getRange(range).setNumberFormat(format);s.getRange(range).format.horizontalAlignment='right';}
function conditional(s,range){s.getRange(range).conditionalFormats.add('containsText',{text:'待',format:{fill:colors.amber}});}
function input(s,range){s.getRange(range).format.fill=colors.amber;}
function summaryTable(s,headers,at,width=11){table(s,headers,[],at);s.getRange(`A${at}:${col(width-1)}${at}`).format.rowHeight=34;}

async function loadData(){
  const d1=await lines('runs/d1/all_8_methods_per_pair.jsonl');
  const d1s=await json('runs/d1/all_8_methods_summary.json');
  const d1perf=await json('runs/d1/performance_accounting.json');
  const d1pairs=await lines('data/d1/evaluation/pairs.jsonl');
  const d1frames=await lines('data/d1/algorithm/frames.jsonl');
  const d1obs=await lines('data/d1/algorithm/observations.jsonl');
  const d2sum=await lines('runs/d2/test/summary.jsonl');
  if(policies.some(p=>!d2sum.some(s=>s.policy===p)))throw Error('D2 final five-policy test output not complete');
  const d2frames=await lines('data/d2/frames.jsonl'),proxy=await lines('data/d2/proxy_events.jsonl');
  const d2events=[],d2requests=[];
  for(const p of policies){
    const es=await lines(`runs/d2/test/${p}/events.jsonl`),rs=await lines(`runs/d2/test/${p}/requests.jsonl`);
    for(const e of es)d2events.push({...e,policy:p});
    for(const r of rs)d2requests.push({...r,policy:p});
  }
  return {d1,d1s,d1perf,d1pairs,d1frames,d1obs,d2sum,d2frames,proxy,d2events,d2requests};
}

function makeResults(d){
  const wb=Workbook.create();
  const s=base(wb,'比较结果','两个方向预实验结果',[222,82,84,84,86,84,90,94,102,98,250],43);s.tabColor=colors.navy;
  const pairSheet=base(wb,'方向一配对','方向一逐配对结果',[220,198,154,84,88,86,100,102,220,220,136,230],d.d1.length+7);
  const eventSheet=base(wb,'方向二事件','方向二逐代理事件',[125,300,110,110,90,100,100,92,92,92,92,110,190],d.d2events.length+7);
  const requestSheet=base(wb,'方向二请求','方向二逐请求记录',[125,290,112,120,100,100,110,102,112,86,100,112,112,112,140],d.d2requests.length+7);
  const sourceSheet=base(wb,'场景来源','场景分组与来源',[90,150,150,160,100,100,380,240,440],20);
  const metricSheet=base(wb,'方法指标','日志指标与分类代理结果',[125,115,115,115,125,120,125,125,115,115,115,115,115],58);
  note(s,3,'真实公开数据和真实本地模型；本轮独立人工复核、风险事件指标仍未测。','K');
  note(pairSheet,3,'发布方身份标签初测；真实独立场地及双人复核未确认。原始分母包含待确认和失败。');
  note(eventSheet,3,'仅自动家具可见性代理；首次足够可判定时刻、风险类别和人工事件真值未测。','M');
  note(requestSheet,3,'逻辑请求含记录回放；结束时延不等同可用答案时延，费用只含本地API收费。','O');
  note(sourceSheet,3,'每行一个来源序列；相同visit/相同场景系列保持同组。公开许可不代表新采集或新人工复核。','I');
  note(metricSheet,3,'来源为各策略test/summary.json；保留未测，绝不把失败或缺失写成零。','M');
  const frame1=new Map(d.d1frames.map(f=>[f.frame_id,f]));
  const pRows=d.d1.map(r=>[r.pair_id,r.method,r.split,r.same_object?1:0,r.decision,r.outcome,r.margin,r.decision_seconds,r.left_observation_id,r.right_observation_id,r.stratum,'未完成独立人工复核']);
  const pr=table(pairSheet,['配对ID','方法代码','划分','同物标签1','决定','结果','决策余量','末端判定秒','左观测ID','右观测ID','配对类型','证据状态'],pRows,5,'D1PairRecords');
  pairSheet.freezePanes.freezeRows(5);pairSheet.freezePanes.freezeColumns(2);fmt(pairSheet,`G6:H${pr.end}`,'0.000000');
  pairSheet.getRange(`E6:F${pr.end}`).conditionalFormats.add('containsText',{text:'error',format:{fill:colors.red}});
  const eRows=d.d2events.map(e=>[e.policy,e.event_id,String(e.video_id),String(e.visit_id??''),e.class_name,e.start_s,e.end_s,...[2,5,10,20].map(t=>e.timely_by_deadline[String(t)]?1:0),e.first_matched_return_s??'未匹配','代理标签待人工复核']);
  const er=table(eventSheet,['策略','事件ID','视频ID','visit分组','代理类别','代理开始秒','代理结束秒','2秒命中1','5秒命中1','10秒命中1','20秒命中1','首次匹配返回秒','标签状态'],eRows,5,'D2EventRecords');
  eventSheet.freezePanes.freezeRows(5);eventSheet.freezePanes.freezeColumns(2);fmt(eventSheet,`F6:G${er.end}`,'0.000');fmt(eventSheet,`L6:L${er.end}`,'0.000');
  const rRows=d.d2requests.map(r=>[r.policy,r.request_id,String(r.video_id),r.execution_mode,r.source_pts_s,r.completed_at_s,r.completed_at_s-r.source_pts_s,r.resolution,r.response.status,r.attempts.length,r.image_bytes*r.attempts.length,r.execution_mode==='real_http'?r.attempts.reduce((a,x)=>a+x.http_request_body_bytes,0):0,r.api_cost??0,r.response.status==='ok'&&r.response.result?.quality_usable===true&&r.status_at_video_end==='completed'?1:0,r.status_at_video_end]);
  const rr=table(requestSheet,['策略','请求ID','视频ID','执行方式','来源秒','完成秒','结束时延秒','长边像素','输出状态','尝试次数','逻辑图片字节','新增HTTP体字节','API美元','可用完成1','视频结束时状态'],rRows,5,'D2RequestRecords');
  requestSheet.freezePanes.freezeRows(5);requestSheet.freezePanes.freezeColumns(2);fmt(requestSheet,`E6:G${rr.end}`,'0.000');fmt(requestSheet,`K6:L${rr.end}`,'#,##0');fmt(requestSheet,`M6:M${rr.end}`,'0.00');
  const sourceRows=[];
  for(const f of d.d1frames.filter((v,i,a)=>a.findIndex(x=>x.sequence_id===v.sequence_id)===i))sourceRows.push(['方向一',f.split,f.sequence_id,'独立场地未核实',d.d1frames.filter(x=>x.sequence_id===f.sequence_id).length,d.d1pairs.filter(x=>x.sequence_id===f.sequence_id).length,'https://rgbd-dataset.cs.washington.edu/dataset/rgbd-scenes/','非商业科研及教育','照片真实；帧时间缺失；可能跨序列共享同一实物']);
  for(const f of d.d2frames.filter((v,i,a)=>a.findIndex(x=>x.video_id===v.video_id)===i))sourceRows.push(['方向二',f.split,String(f.video_id),String(f.visit_id),d.d2frames.filter(x=>x.video_id===f.video_id).length,d.proxy.filter(x=>x.video_id===f.video_id).length,'https://github.com/apple/ARKitScenes','见本地LICENSE_ARKitScenes.txt','真实MOV；visit不是已核实独立家庭；事件是自动几何代理']);
  table(sourceSheet,['方向','划分','序列ID','分组','采样帧数','配对或事件数','来源网址','许可','主要限制'],sourceRows,5,'SourceRecords');sourceSheet.freezePanes.freezeRows(5);
  const metricRows=policies.map(p=>{const z=d.d2sum.find(s=>s.policy===p);return [p,z.recorded_e2e_p50_s,z.recorded_e2e_p95_s,empty(z.usable_response_conditional_p50_s),empty(z.usable_response_conditional_p95_s),z.encoded_image_bytes_all_logical_attempts,z.actual_http_request_body_bytes,z.api_cost,z.unknown_answer_ticks,z.ticks,z.proxy_stale_answer_ticks,z.scheduler_p50_ms,z.scheduler_p95_ms]});
  table(metricSheet,['策略','结束P50秒','结束P95秒','可用条件P50秒','可用条件P95秒','逻辑图片字节','新增HTTP体字节','API美元','未知答案采样数','总采样数','过期代理采样数','调度P50毫秒','调度P95毫秒'],metricRows,5,'D2MetricRecords');fmt(metricSheet,'B6:E10','0.000');fmt(metricSheet,'F6:G10','#,##0');fmt(metricSheet,'H6:H10','0.00');fmt(metricSheet,'L6:M10','0.000');
  note(metricSheet,12,'可用条件分位数只含有效且在视频结束前完成的答案；全部请求有效分位数可能未测。','M');
  note(metricSheet,13,'API费用0不含电费、设备折旧；调用减少不能换算成已节省金额。','M');
  const classes=policies.flatMap(p=>Object.entries(d.d2sum.find(s=>s.policy===p).per_class).map(([c,z])=>[p,c,z.n,empty(z.proxy_recall_by_deadline['5']),empty(z.proxy_recall_by_deadline['20']),z.n===0?'无样本，未测':'家具可见性代理']));
  table(metricSheet,['策略','代理类别','事件分母','5秒代理召回','20秒代理召回','证据范围'],classes,16,'D2ClassMetrics');fmt(metricSheet,'D17:E46','0.0%');
  table(metricSheet,['方向一计时项','数值','单位','记录范围'],[
    ['初次整体流程',d.d1perf.initial_integrated_wall_seconds,'秒','7方法初次运行'],
    ['特征完整阶段',d.d1perf.feature_extraction_wall_including_model_load_crops_quality_preprocessing_forward_and_save_seconds,'秒','含模型加载/质量/前向'],
    ['编码器前向',d.d1perf.encoder_forward_seconds,'秒','真实CPU测量'],
    ['共享几何和匹配',d.d1perf.frame_pair_shared_geometry_matching_preparation_seconds,'秒','45个帧对'],
    ['质量单独计时','未测','秒','含在特征阶段内'],
    ['付费API',d.d1perf.api_charge_usd,'美元','电费及能耗未测']
  ],49,'D1Timing');fmt(metricSheet,'B50:B55','0.000');metricSheet.getRange('A50:D55').format.wrapText=true;metricSheet.getRange('A50:D55').format.rowHeight=36;
  note(s,5,'方向一 探索留出24对','K');
  summaryTable(s,['方法','配对数','误合并','漏合并','待确认','失败','自动数','自动比例','已判错误率','完整率','说明'],6);
  for(let i=0;i<d1methods.length;i++){
    const r=7+i,m=d1methods[i];s.getRange(`A${r}`).values=[[m]];s.getRange(`K${r}`).values=[[methodNames[m]]];
    const method=`'方向一配对'!$B$6:$B$${pr.end},$A${r},'方向一配对'!$C$6:$C$${pr.end},"exploratory_holdout"`;
    s.getRange(`B${r}:J${r}`).formulas=[[
      `=COUNTIFS(${method})`,
      `=COUNTIFS(${method},'方向一配对'!$D$6:$D$${pr.end},0,'方向一配对'!$E$6:$E$${pr.end},"same")`,
      `=COUNTIFS(${method},'方向一配对'!$D$6:$D$${pr.end},1,'方向一配对'!$E$6:$E$${pr.end},"different")`,
      `=COUNTIFS(${method},'方向一配对'!$E$6:$E$${pr.end},"pending")`,
      `=COUNTIFS(${method},'方向一配对'!$E$6:$E$${pr.end},"failed")`,
      `=B${r}-E${r}-F${r}`,`=IF(B${r}=0,"未测",G${r}/B${r})`,`=IF(G${r}=0,"未测",(C${r}+D${r})/G${r})`,`=IF(B${r}=0,"未测",(B${r}-F${r})/B${r})`
    ]];
  }
  fmt(s,'H7:J14','0.0%');note(s,16,'B/C开发自动判定目标80%，实际均83.3%；测试比例不同，必须同时看错误率。','K');
  note(s,17,'C与去关系消融相同；取消待确认后B/C都漏合并3对。尚无关系模块额外收益。','K');
  note(s,20,'方向二 留出视频的家具可见性代理','K');
  summaryTable(s,['策略','逻辑请求','新增HTTP','记录回放','代理事件','5秒命中','5秒召回','20秒召回','失败输出','未完成','说明'],21);
  for(let i=0;i<policies.length;i++){
    const r=22+i,p=policies[i];s.getRange(`A${r}`).values=[[p]];s.getRange(`K${r}`).values=[[methodNames[p]]];
    const rq=`'方向二请求'!$A$6:$A$${rr.end},$A${r}`,ev=`'方向二事件'!$A$6:$A$${er.end},$A${r}`;
    s.getRange(`B${r}:J${r}`).formulas=[[
      `=COUNTIFS(${rq})`,`=COUNTIFS(${rq},'方向二请求'!$D$6:$D$${rr.end},"real_http")`,`=COUNTIFS(${rq},'方向二请求'!$D$6:$D$${rr.end},"recorded_response")`,`=COUNTIFS(${ev})`,`=COUNTIFS(${ev},'方向二事件'!$I$6:$I$${er.end},1)`,`=IF(E${r}=0,"未测",F${r}/E${r})`,`=IF(E${r}=0,"未测",COUNTIFS(${ev},'方向二事件'!$K$6:$K$${er.end},1)/E${r})`,`=COUNTIFS(${rq},'方向二请求'!$I$6:$I$${rr.end},"invalid")+COUNTIFS(${rq},'方向二请求'!$I$6:$I$${rr.end},"error")`,`=COUNTIFS(${rq},'方向二请求'!$O$6:$O$${rr.end},"unfinished")`
    ]];
  }
  fmt(s,'G22:H26','0.0%');note(s,28,'人工事件召回、关键风险类别、质量非劣效和实际费用节省：未测。','K');
  note(s,29,'采样帧为真实画面；代理事件来自几何投影，不能替代人工“首次足够可判定时刻”。','K');
  summaryTable(s,['策略','可用完成','结束P50秒','结束P95秒','可用P50秒','可用P95秒','逻辑图MB','新增体MB','API美元','未知比例','过期采样数'],32);
  for(let i=0;i<policies.length;i++){
    const r=33+i,mr=6+i;s.getRange(`A${r}`).values=[[policies[i]]];
    s.getRange(`B${r}:K${r}`).formulas=[[
      `=COUNTIFS('方向二请求'!$A$6:$A$${rr.end},$A${r},'方向二请求'!$N$6:$N$${rr.end},1)`,`='方法指标'!B${mr}`,`='方法指标'!C${mr}`,`='方法指标'!D${mr}`,`='方法指标'!E${mr}`,`='方法指标'!F${mr}/1000000`,`='方法指标'!G${mr}/1000000`,`='方法指标'!H${mr}`,`=IF('方法指标'!J${mr}=0,"未测",'方法指标'!I${mr}/'方法指标'!J${mr})`,`='方法指标'!K${mr}`
    ]];
  }
  fmt(s,'C33:I37','0.000');fmt(s,'J33:J37','0.0%');note(s,39,'结束时延含错误/超时；可用P50/P95为条件分位数。缓存读取速度未用作推理时延。','K');note(s,40,'API收费为0美元；电费、设备能耗及真机性能未测。','K');
  return {wb,summary:s,pairSheet,d,renderViews:[['比较结果','A1:K18'],['比较结果','A20:K40'],['方向一配对','A1:H17'],['方向二事件','A1:M16'],['方向二请求','A1:O16'],['场景来源','A1:I16'],['方法指标','A1:M14'],['方法指标','A16:F28'],['方法指标','A41:F55']]};
}

function makeReview(d){
  const wb=Workbook.create(),links=[];
  function nativeLink(s,sheetIndex,cell,p,label){s.getRange(cell).values=[[label]];s.getRange(cell).format.font.color='#1765AD';links.push({sheetIndex,cell,target:linkTarget(p)});}
  const pair=base(wb,'对象复核','方向一独立复核',[225,155,95,95,160,160,112,130,155,112,130,155,112,130,155,155],d.d1pairs.length+7);pair.tabColor=colors.navy;
  const event=base(wb,'事件复核','方向二事件独立复核',[
    300,84,95,95,100,110,110,
    120,160,120,120,150,130,155,
    120,160,120,120,150,130,155,
    120,160,120,120,150,130,155,
    170,145,145,145
  ],d.proxy.length+7);
  const collect=base(wb,'最小采集','补足真实任务的最小采集',[210,90,95,95,350,110,125,145,165,140],65);
  note(pair,3,'两位真实复核人各在空白副本独立填写，再按配对ID合并；不要先看发布方答案或算法结果。','P');
  note(pair,4,'黄格为待填字段；必须不同复核人并记录时间。分歧须另行裁决，不代填任何人类确认。','P');
  const obs=new Map(d.d1obs.map(x=>[x.observation_id,x])),frames=new Map(d.d1frames.map(x=>[x.frame_id,x]));
  const rows=d.d1pairs.map(p=>[p.pair_id,p.split,null,null,obs.get(p.left_observation_id).bbox_xyxy.join(', '),obs.get(p.right_observation_id).bbox_xyxy.join(', '),null,null,null,null,null,null,null,null,null,null]);
  const pr=table(pair,['配对ID','划分','左图','右图','左框xyxy像素','右框xyxy像素','复核1判断','复核1人ID','复核1时间','复核2判断','复核2人ID','复核2时间','裁决判断','裁决人ID','裁决时间','记录状态'],rows,5,'PairReview');
  for(let i=0;i<d.d1pairs.length;i++){
    const r=6+i,p=d.d1pairs[i];nativeLink(pair,1,`C${r}`,frames.get(p.left_frame_id).image_path,'查看左图');nativeLink(pair,1,`D${r}`,frames.get(p.right_frame_id).image_path,'查看右图');
    pair.getRange(`P${r}`).formulas=[[`=IF(OR(G${r}="",H${r}="",I${r}="",J${r}="",K${r}="",L${r}=""),"待两人复核",IF(H${r}=K${r},"需不同复核人",IF(G${r}=J${r},"已记录一致判断",IF(OR(M${r}="",N${r}="",O${r}=""),"待裁决","已记录裁决"))))`]];
  }
  input(pair,`G6:O${pr.end}`);for(const c of ['G','J','M'])pair.getRange(`${c}6:${c}${pr.end}`).dataValidation={rule:{type:'list',values:['同物','异物','不确定']}};
  for(const c of ['I','L','O'])fmt(pair,`${c}6:${c}${pr.end}`,'yyyy-mm-dd hh:mm');conditional(pair,`P6:P${pr.end}`);pair.freezePanes.freezeRows(5);pair.freezePanes.freezeColumns(2);
  note(event,3,'代理开始/结束只供定位，不是人工真值。类别、位置、可判时刻、可见结束和状态变化均由两人独立填写。','AC');
  note(event,4,'先各填空白副本再合并；须补充代理遗漏事件。链接指向当前工作区；搬移数据后需重新生成。','AC');
  event.getRange('AD3').values=[['关键范围未批准：留空或待确认。']];
  event.getRange('AD4').values=[['新增标记不参与原记录状态公式。']];
  event.getRange('AD3:AF4').format.font.color=colors.muted;
  const f2=new Map(d.d2frames.map(f=>[f.frame_id,f]));
  const ers=d.proxy.map(e=>[e.event_id,e.split,null,null,e.class_name,e.start_s,e.end_s,...Array(25).fill(null)]);
  const er=table(event,['事件ID','划分','原视频','首帧','代理类别','代理始秒','代理末秒','复核1类别','复核1位置','复核1可判秒','复核1结束秒','复核1状态变化','复核1人ID','复核1时间','复核2类别','复核2位置','复核2可判秒','复核2结束秒','复核2状态变化','复核2人ID','复核2时间','裁决类别','裁决位置','裁决可判秒','裁决结束秒','裁决状态变化','裁决人ID','裁决时间','记录状态','复核1关键类别','复核2关键类别','裁决关键类别'],ers,5,'EventReview');
  for(let i=0;i<d.proxy.length;i++){
    const r=6+i,e=d.proxy[i],frame=f2.get(e.frames[0]?.frame_id);if(frame){nativeLink(event,2,`C${r}`,frame.source_video,'打开视频');nativeLink(event,2,`D${r}`,frame.path,'查看首帧');}
    event.getRange(`AC${r}`).formulas=[[`=IF(OR(H${r}="",I${r}="",J${r}="",K${r}="",L${r}="",M${r}="",N${r}="",O${r}="",P${r}="",Q${r}="",R${r}="",S${r}="",T${r}="",U${r}=""),"待两人复核",IF(M${r}=T${r},"需不同复核人",IF(AND(H${r}=O${r},I${r}=P${r},J${r}=Q${r},K${r}=R${r},L${r}=S${r}),"已记录一致判断",IF(OR(V${r}="",W${r}="",X${r}="",Y${r}="",Z${r}="",AA${r}="",AB${r}=""),"待裁决","已记录裁决"))))`]];
  }
  input(event,`H6:AB${er.end}`);for(const c of ['F','G','J','K','Q','R','X','Y'])fmt(event,`${c}6:${c}${er.end}`,'0.000');for(const c of ['N','U','AB'])fmt(event,`${c}6:${c}${er.end}`,'yyyy-mm-dd hh:mm');conditional(event,`AC6:AC${er.end}`);event.freezePanes.freezeRows(5);event.freezePanes.freezeColumns(2);
  input(event,`AD6:AF${er.end}`);event.getRange(`AD6:AF${er.end}`).dataValidation={rule:{type:'list',values:['是','否','待确认']}};
  note(collect,3,'目标3个独立授权场地，每处2组静态布置×8张，共48张；另拍每处2段1–2分钟视频，共6段。','J');
  note(collect,4,'物体移动后另建布置组。同场地全部衍生图/视频同组；复核与质量门槛在测试前确认。','J');
  const crows=[],views=['正面','左侧','右侧','远景','近景','局部遮挡','近重复','离开后重访'];
  for(let si=1;si<=3;si++)for(let gi=1;gi<=2;gi++)for(let vi=1;vi<=8;vi++)crows.push([`S0${si}_G0${gi}_P${String(vi).padStart(2,'0')}.jpg`,'照片',`S0${si}`,`G0${gi}`,`${views[vi-1]}；线缆、箱子，含相似但不同实物`,null,null,null,null,'待采集']);
  for(let si=1;si<=3;si++)for(let vi=1;vi<=2;vi++)crows.push([`S0${si}_V0${vi}.mov`,'视频',`S0${si}`,`V0${vi}`,vi===1?'重复画面、小目标、局部变化':'短暂出现、遮挡、真实状态变化',120,null,null,null,'待采集']);
  const cr=table(collect,['计划文件名','类型','独立场地','布置或视频组','计划覆盖内容','目标时长秒','拍摄人','授权记录','真实拍摄时间','状态'],crows,5,'CapturePlan');input(collect,`G6:I${cr.end}`);fmt(collect,`I6:I${cr.end}`,'yyyy-mm-dd hh:mm');collect.freezePanes.freezeRows(5);collect.freezePanes.freezeColumns(1);
  note(collect,61,'采集只摆放安全的静态对象，不制造真实危险；确保空间及影像使用授权。','J');note(collect,62,'至少1个场地开发、2个场地留出；参数只用开发选。真实问题和身份答案另存，不输入算法。','J');
  return {wb,pair,event,links,renderViews:[['对象复核','A1:I16'],['对象复核','J5:P16'],['事件复核','A1:N13'],['事件复核','O5:AC13'],['最小采集','A1:J16'],['最小采集','A49:J62'],['事件复核','AC1:AF14']]};
}

// Artifact tool's documented API has no native hyperlink writer and its formula
// evaluator returns "HYPERLINK is not implemented". Only the missing hyperlink
// relationship is added with OOXML; all cells/styles/formulas are artifact-authored.
async function addNativeHyperlinks(filename,links){
  if(!links?.length)return;
  for(const l of links)await fs.access(fileURLToPath(l.target));
  const python='/Users/wangkai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
  const code=String.raw`import sys,json,zipfile,xml.etree.ElementTree as E
filename=sys.argv[1]; links=json.load(sys.stdin)
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'; P='http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('',S); E.register_namespace('r',R)
with zipfile.ZipFile(filename) as z: parts={i.filename:z.read(i.filename) for i in z.infolist()}
post={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
for si in sorted({x['sheetIndex'] for x in links}):
    sp=f'xl/worksheets/sheet{si}.xml'; rp=f'xl/worksheets/_rels/sheet{si}.xml.rels'
    sheet=E.fromstring(parts[sp]); rels=E.fromstring(parts[rp]) if rp in parts else E.Element('{'+P+'}Relationships')
    hyperlinks=E.Element('{'+S+'}hyperlinks'); ids={r.get('Id') for r in rels}
    for n,l in enumerate(x for x in links if x['sheetIndex']==si):
        rid='rIdReviewLink'+str(n+1); assert rid not in ids
        E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':l['target'],'TargetMode':'External'})
        E.SubElement(hyperlinks,'{'+S+'}hyperlink',{'ref':l['cell'],'{'+R+'}id':rid})
    position=next((i for i,c in enumerate(sheet) if c.tag.rsplit('}',1)[-1] in post),len(sheet));sheet.insert(position,hyperlinks)
    parts[sp]=E.tostring(sheet,encoding='utf-8',xml_declaration=True);parts[rp]=E.tostring(rels,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(filename,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in parts.items():z.writestr(name,data)
print(json.dumps({'native_hyperlinks':len(links),'all_targets_exist':True}))`;
  const r=spawnSync(python,['-c',code,filename],{input:JSON.stringify(links),encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);console.log(r.stdout.trim());
}

async function qaAndExport(product,name){
  const {wb}=product;wb.recalculate();
  const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'formula error scan'});
  await fs.writeFile(path.join(QA,name+'_error_scan.ndjson'),err.ndjson);
  if(/"(?:value|text)"\s*:\s*"#(?:REF|DIV|VALUE|NAME|N\/A|NUM|NULL|SPILL|CALC)/.test(err.ndjson))throw Error('Formula error found: '+err.ndjson);
  const checks={};
  if(product.summary){
    const vals=product.summary.getRange('B7:J14').values;
    for(let i=0;i<d1methods.length;i++){
      const x=product.d.d1s.find(s=>s.method===d1methods[i]&&s.split==='exploratory_holdout');
      const expected=[x.pairs,x.false_merges,x.missed_merges,x.pending,x.failed,x.automatic_count,x.automatic_fraction,x.decided_error_rate,x.result_completeness];
      for(let j=0;j<expected.length;j++)if(typeof vals[i][j]!=='number'||!Number.isFinite(vals[i][j])||Math.abs(vals[i][j]-expected[j])>1e-9)throw Error(`D1 reconciliation ${i},${j}: ${vals[i][j]} vs ${expected[j]}`);
    }
    checks.d1_summary_reconciles=true;
    const rawRow=6+product.d.d1.findIndex(r=>r.method==='A_original'&&r.split==='exploratory_holdout');
    const cell=product.pairSheet.getRange(`E${rawRow}`),old=cell.values[0][0],before=product.summary.getRange('F7').values[0][0];
    cell.values=[['failed']];wb.recalculate();if(product.summary.getRange('F7').values[0][0]!==before+1)throw Error('COUNTIFS failed to respond to temporary input');cell.values=[[old]];wb.recalculate();if(product.summary.getRange('F7').values[0][0]!==before)throw Error('Input restore failed');
    checks.temporary_input_changed_summary_and_restored=true;
    const d2vals=product.summary.getRange('B22:J26').values;
    for(let i=0;i<policies.length;i++){
      const x=product.d.d2sum.find(s=>s.policy===policies[i]);
      const expected=[x.logical_requests,x.new_real_http_requests,x.recorded_responses_replayed,x.proxy_events,x.proxy_recall_by_deadline['5']*x.proxy_events,x.proxy_recall_by_deadline['5'],x.proxy_recall_by_deadline['20'],x.request_status_counts.invalid+x.request_status_counts.error,x.unfinished_at_video_end];
      for(let j=0;j<expected.length;j++)if(typeof d2vals[i][j]!=='number'||!Number.isFinite(d2vals[i][j])||Math.abs(d2vals[i][j]-expected[j])>1e-9)throw Error(`D2 reconciliation ${i},${j}: ${d2vals[i][j]} vs ${expected[j]}`);
    }
    checks.d2_summary_reconciles=true;
    await fs.writeFile(path.join(QA,name+'_summary.ndjson'),(await wb.inspect({kind:'table',range:'比较结果!A6:K14',include:'values,formulas',tableMaxRows:10,tableMaxCols:11,maxChars:7000})).ndjson);
  }
  if(product.pair){
    const s=product.pair;const original=s.getRange('G6:O6').values;
    if(s.getRange('P6').values[0][0]!=='待两人复核')throw Error('Blank human review must stay pending');
    s.getRange('G6:I6').values=[['同物','TEMP_TEST_REVIEWER_1',45000]];wb.recalculate();
    if(s.getRange('P6').values[0][0]!=='待两人复核')throw Error('One reviewer must not complete review');
    s.getRange('J6:L6').values=[['同物','TEMP_TEST_REVIEWER_2',45000.1]];wb.recalculate();
    if(s.getRange('P6').values[0][0]!=='已记录一致判断')throw Error('Two-reviewer formula failed');
    s.getRange('G6:O6').values=original;wb.recalculate();
    if(s.getRange('P6').values[0][0]!=='待两人复核')throw Error('Human review temporary input restoration failed');
    checks.review_blank_one_two_restored=true;
  }
  wb.recalculate();
  for(let i=0;i<product.renderViews.length;i++){
    const [sheetName,range]=product.renderViews[i];const blob=await wb.render({sheetName,range,scale:1.3,format:'png'});
    await fs.writeFile(path.join(QA,`${name}_${i+1}_${sheetName}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
  const filename=path.join(OUT,name+'.xlsx'),output=await SpreadsheetFile.exportXlsx(wb);await output.save(filename);await addNativeHyperlinks(filename,product.links);
  await fs.writeFile(path.join(QA,name+'_checks.json'),JSON.stringify(checks,null,2));
  console.log(JSON.stringify({file:name+'.xlsx',sheets:product.renderViews.map(x=>x[0]).filter((x,i,a)=>a.indexOf(x)===i),checks}));
}

await fs.mkdir(QA,{recursive:true});await fs.mkdir(OUT,{recursive:true});
const data=await loadData();
await qaAndExport(makeResults(data),'预实验结果');
await qaAndExport(makeReview(data),'补充复核');
