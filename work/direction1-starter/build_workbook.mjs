import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const DIR = '/Users/wangkai/Documents/ChatGPT/温肯科研/work/direction1-starter';
const OUT = '/Users/wangkai/Desktop/温肯科研/08_采集标注表.xlsx';
const wb = Workbook.create();
const names = ['填写说明','汇总','场景登记','照片登记','目标标注','配对真值','方法结果'];
const S = Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const caps = {场景登记:20,照片登记:160,目标标注:400,配对真值:120,方法结果:360};
const end = n => caps[n]+5;
const col = i => {let s=''; for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;};
const R=(n,c)=>`'${n}'!$${c}$6:$${c}$${end(n)}`;
const pick=(key,n,c)=>`IF(COUNTIF(${R(n,'A')},${key})=1,INDEX(${R(n,c)},MATCH(${key},${R(n,'A')},0)),"")`;
const checks=(empty,tests)=>`=IF(${empty},"",${tests.reduceRight((v,[c,msg])=>`IF(${c},"${msg}",${v})`,'"可用"')})`;
const font='PingFang SC';
function fmt(sh,range,opt){sh.getRange(range).format=opt;}
function label(sh,addr,value){sh.getRange(addr).values=[[value]];}
function formula(sh,addr,value){sh.getRange(addr).formulas=[[value]];}
function fill(sh,c,first,last,fn){sh.getRange(`${c}${first}:${c}${last}`).formulas=Array.from({length:last-first+1},(_,i)=>[fn(first+i)]);}
function list(sh,range,values){sh.getRange(range).dataValidation={rule:{type:'list',values}};}
function table(n,heads,inputCols,widths,note){
 const sh=S[n],last=col(heads.length-1),e=end(n);
 sh.showGridLines=false;
 fmt(sh,`A1:${last}${e}`,{font:{name:font,size:11,color:'#243348'},verticalAlignment:'center',rowHeight:25});
 label(sh,'A2',n);fmt(sh,'A2',{font:{name:font,size:16,bold:true}});
 label(sh,'A3',note);fmt(sh,`A3:${last}3`,{font:{name:font,size:10,color:'#526174'},rowHeight:24});
 sh.getRange(`A5:${last}5`).values=[heads];
 const t=sh.tables.add(`A5:${last}${e}`,true,'CaptureTable'+names.indexOf(n));t.style='TableStyleLight9';t.showFilterButton=true;
 fmt(sh,`A5:${last}5`,{fill:'#334860',font:{name:font,size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:48,horizontalAlignment:'center'});
 fmt(sh,`A6:${col(inputCols-1)}${e}`,{fill:'#FFF6DC'});
 if(inputCols<heads.length)fmt(sh,`${col(inputCols)}6:${last}${e}`,{fill:'#F0F3F6',font:{name:font,size:11,color:'#334860'}});
 widths.forEach((w,i)=>fmt(sh,`${col(i)}1:${col(i)}${e}`,{columnWidth:w}));
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);
 sh.tabColor='#A6B5C4';
 return sh;
}

const scene=table('场景登记',['场景ID','场地组ID','场景简称','场景类型','采集许可','云端上传许可','隐私处理','分组','采集人代号','登记日期','许可记录位置','备注','记录检查 自动'],12,[14,15,19,14,16,18,16,13,16,15,23,26,22],'浅黄色填写；同一真实场地的所有房间和布置必须属于同一分组。');
list(scene,'D6:D25',['办公室','宿舍','授权住宅','教室','其他']);list(scene,'E6:E25',['已获许可','未确认','不允许']);list(scene,'F6:F25',['已获许可','仅本地','未确认']);list(scene,'G6:G25',['无隐私','已处理','待处理']);list(scene,'H6:H25',['开发','测试']);fmt(scene,'J6:J25',{numberFormat:'yyyy-mm-dd'});
fill(scene,'M',6,25,r=>checks(`COUNTA(A${r}:L${r})=0`,[
 [`OR(A${r}="",B${r}="",C${r}="",H${r}="",I${r}="",K${r}="")`,'请补必填项'],
 [`COUNTIF($A$6:$A$25,A${r})<>1`,'场景ID重复'],
 [`E${r}<>"已获许可"`,'采集许可待确认'],
 [`AND(G${r}<>"无隐私",G${r}<>"已处理")`,'隐私处理待确认'],
 [`AND(H${r}<>"开发",H${r}<>"测试")`,'分组无效'],
 [`AND(COUNTIFS($B$6:$B$25,B${r},$H$6:$H$25,"开发")>0,COUNTIFS($B$6:$B$25,B${r},$H$6:$H$25,"测试")>0)`,'同场地分组冲突']
 ]));

const photo=table('照片登记',['照片ID','场景ID','布置组ID','照片文件名','拍摄日期','拍摄视角','遮挡程度','画质','隐私检查','使用状态','备注','场地组 自动','分组 自动','记录检查 自动','真实来源ID 可选','原始时间戳 毫秒 可选','帧序号 可选','元数据说明'],11,[15,14,16,27,16,17,15,13,16,14,25,16,13,23,23,26,18,36],'每组布置拍8张；物体位置或关系改变时，新建布置组。右侧保留真实来源和拍摄元数据。');
fmt(photo,`O6:R${end('照片登记')}`,{fill:'#FFF6DC',font:{name:font,size:11,color:'#243348'}});
fmt(photo,`P6:Q${end('照片登记')}`,{numberFormat:'0'});
photo.getRange(`P6:P${end('照片登记')}`).dataValidation={rule:{type:'decimal',operator:'greaterThanOrEqual',formula1:0}};
photo.getRange(`Q6:Q${end('照片登记')}`).dataValidation={rule:{type:'whole',operator:'greaterThanOrEqual',formula1:0}};
list(photo,`F6:F${end('照片登记')}`,['正面','左侧','右侧','近景','远景','部分遮挡','近重复','离开后重访']);list(photo,`G6:G${end('照片登记')}`,['无遮挡','部分遮挡','完全遮挡']);list(photo,`H6:H${end('照片登记')}`,['可用','模糊','过暗','过曝']);list(photo,`I6:I${end('照片登记')}`,['无隐私','已处理','待处理']);list(photo,`J6:J${end('照片登记')}`,['使用','排除']);fmt(photo,`E6:E${end('照片登记')}`,{numberFormat:'yyyy-mm-dd'});
fill(photo,'L',6,end('照片登记'),r=>`=IF(B${r}="","",${pick(`B${r}`,'场景登记','B')})`);
fill(photo,'M',6,end('照片登记'),r=>`=IF(B${r}="","",${pick(`B${r}`,'场景登记','H')})`);
fill(photo,'N',6,end('照片登记'),r=>checks(`AND(COUNTA(A${r}:K${r})=0,COUNTA(O${r}:R${r})=0)`,[
 [`OR(A${r}="",B${r}="",C${r}="",D${r}="",F${r}="",G${r}="",H${r}="",J${r}="")`,'请补必填项'],
 [`COUNTIF($A$6:$A$165,A${r})<>1`,'照片ID重复'],
 [`COUNTIF(${R('场景登记','A')},B${r})<>1`,'场景ID无效'],
 [`${pick(`B${r}`,'场景登记','M')}<>"可用"`,'场景记录未就绪'],
 [`J${r}="排除"`,'已排除'],
 [`OR(H${r}<>"可用",AND(I${r}<>"无隐私",I${r}<>"已处理"))`,'画质或隐私待处理']
 ]));

const target=table('目标标注',['观察ID','照片ID','真实对象ID','问题ID 可选','对象类别','位置关系 真值','可见性','x1 左 0至1','y1 上 0至1','x2 右 0至1','y2 下 0至1','标注人代号','复核人代号','复核状态','备注','场地组 自动','分组 自动','布置组 自动','记录检查 自动'],15,[16,15,18,18,15,24,15,13,13,13,13,16,16,18,26,16,13,17,23],'一行是一张照片中的一个对象。A/B/C共享核验后的候选框；人工身份ID和关系真值仅用于评分。');
list(target,`E6:E${end('目标标注')}`,['线缆','箱子','椅子','其他可见对象']);list(target,`G6:G${end('目标标注')}`,['完整可见','部分可见','完全不可见']);list(target,`N6:N${end('目标标注')}`,['未复核','两人一致','已裁决','有争议']);
for(const c of ['H','I','J','K'])target.getRange(`${c}6:${c}${end('目标标注')}`).dataValidation={rule:{type:'decimal',operator:'between',formula1:0,formula2:1}};
fmt(target,`H6:K${end('目标标注')}`,{numberFormat:'0.000'});
fill(target,'P',6,end('目标标注'),r=>`=IF(B${r}="","",${pick(`B${r}`,'照片登记','L')})`);
fill(target,'Q',6,end('目标标注'),r=>`=IF(B${r}="","",${pick(`B${r}`,'照片登记','M')})`);
fill(target,'R',6,end('目标标注'),r=>`=IF(B${r}="","",${pick(`B${r}`,'照片登记','C')})`);
fill(target,'S',6,end('目标标注'),r=>checks(`COUNTA(A${r}:O${r})=0`,[
 [`OR(A${r}="",B${r}="",G${r}="",L${r}="",M${r}="")`,'请补必填项'],
 [`COUNTIF($A$6:$A$405,A${r})<>1`,'观察ID重复'],
 [`COUNTIF(${R('照片登记','A')},B${r})<>1`,'照片ID无效'],
 [`${pick(`B${r}`,'照片登记','N')}<>"可用"`,'照片记录未就绪'],
 [`L${r}=M${r}`,'需不同人复核'],
 [`AND(N${r}<>"两人一致",N${r}<>"已裁决")`,'标注待复核'],
 [`G${r}="完全不可见"`,'不可见不计分'],
 [`OR(C${r}="",E${r}="",F${r}="",COUNT(H${r}:K${r})<>4)`,'对象或框待补齐'],
 [`OR(H${r}<0,I${r}<0,J${r}>1,K${r}>1,H${r}>=J${r},I${r}>=K${r})`,'框坐标无效']
 ]));

const pair=table('配对真值',['配对ID','观察A','观察B','初标判定','复核判定','裁决判定','标注人代号','复核人代号','裁决人代号','备注','最终真值 自动','场地组 自动','分组 自动','计分资格 自动','配对检查 自动'],10,[15,16,16,16,16,16,16,16,16,26,18,16,13,18,25],'固定配对清单后，A、B、C使用同一清单；每空间可先选12对，6对同一、6对不同。');
for(const c of ['D','E','F'])list(pair,`${c}6:${c}${end('配对真值')}`,['同一','不同','无法确定']);
fill(pair,'K',6,end('配对真值'),r=>`=IF(A${r}="","",IF(AND(D${r}<>"",D${r}=E${r}),D${r},IF(AND(F${r}<>"",I${r}<>""),F${r},"待复核")))`);
fill(pair,'L',6,end('配对真值'),r=>`=IF(B${r}="","",${pick(`B${r}`,'目标标注','P')})`);
fill(pair,'M',6,end('配对真值'),r=>`=IF(B${r}="","",${pick(`B${r}`,'目标标注','Q')})`);
fill(pair,'O',6,end('配对真值'),r=>checks(`COUNTA(A${r}:J${r})=0`,[
 [`OR(A${r}="",B${r}="",C${r}="",D${r}="",E${r}="",G${r}="",H${r}="")`,'请补必填项'],
 [`COUNTIF($A$6:$A$125,A${r})<>1`,'配对ID重复'],
 [`B${r}=C${r}`,'不能配同一观察'],
 [`COUNTIFS($B$6:$B$125,B${r},$C$6:$C$125,C${r})+COUNTIFS($B$6:$B$125,C${r},$C$6:$C$125,B${r})>1`,'配对重复含反向'],
 [`OR(COUNTIF(${R('目标标注','A')},B${r})<>1,COUNTIF(${R('目标标注','A')},C${r})<>1)`,'观察ID无效'],
 [`OR(${pick(`B${r}`,'目标标注','S')}<>"可用",${pick(`C${r}`,'目标标注','S')}<>"可用")`,'目标记录未就绪'],
 [`${pick(`B${r}`,'目标标注','B')}=${pick(`C${r}`,'目标标注','B')}`,'需不同照片'],
 [`OR(L${r}<>${pick(`C${r}`,'目标标注','P')},M${r}<>${pick(`C${r}`,'目标标注','Q')})`,'场地或分组不一致'],
 [`G${r}=H${r}`,'需不同人复核'],
 [`K${r}="待复核"`,'判定待复核'],
 [`AND(D${r}<>E${r},OR(I${r}=G${r},I${r}=H${r}))`,'需第三人裁决'],
 [`AND(K${r}="同一",${pick(`B${r}`,'目标标注','C')}<>${pick(`C${r}`,'目标标注','C')})`,'真值与对象ID冲突'],
 [`AND(K${r}="不同",${pick(`B${r}`,'目标标注','C')}=${pick(`C${r}`,'目标标注','C')})`,'真值与对象ID冲突']
 ]));
fill(pair,'N',6,end('配对真值'),r=>`=IF(A${r}="","",IF(O${r}<>"可用","暂不计分",IF(OR(K${r}="同一",K${r}="不同"),"可计分","无法确定不计分")))`);

const result=table('方法结果',['配对ID','方法','方法输出','配置版本','耗时 秒','调用次数','费用 人民币','备注','参考真值 自动','分组 自动','计分资格 自动','结果分类 自动','录入检查 自动'],8,[15,19,16,24,14,14,17,28,20,14,19,19,24],'每个配对填A、B、C各一行。空白代表缺结果，不能替代“待确认”。费用与耗时可暂留空。');
list(result,`B6:B${end('方法结果')}`,['A 当前方法','B 简单强基线','C 候选方法']);list(result,`C6:C${end('方法结果')}`,['合并','分开','待确认']);fmt(result,`E6:E${end('方法结果')}`,{numberFormat:'0.00'});fmt(result,`F6:F${end('方法结果')}`,{numberFormat:'0'});fmt(result,`G6:G${end('方法结果')}`,{numberFormat:'0.0000'});
fill(result,'I',6,end('方法结果'),r=>`=IF(A${r}="","",${pick(`A${r}`,'配对真值','K')})`);
fill(result,'J',6,end('方法结果'),r=>`=IF(A${r}="","",${pick(`A${r}`,'配对真值','M')})`);
fill(result,'M',6,end('方法结果'),r=>checks(`COUNTA(A${r}:H${r})=0`,[
 [`OR(A${r}="",B${r}="",C${r}="",D${r}="")`,'请补配对方法输出版本'],
 [`COUNTIF(${R('配对真值','A')},A${r})<>1`,'配对ID无效'],
 [`COUNTIFS($A$6:$A$365,A${r},$B$6:$B$365,B${r})<>1`,'同配对同方法重复'],
 [`AND(B${r}<>"A 当前方法",B${r}<>"B 简单强基线",B${r}<>"C 候选方法")`,'方法无效'],
 [`AND(C${r}<>"合并",C${r}<>"分开",C${r}<>"待确认")`,'方法输出无效'],
 [`OR(AND(E${r}<>"",NOT(ISNUMBER(E${r}))),AND(F${r}<>"",NOT(ISNUMBER(F${r}))),AND(G${r}<>"",NOT(ISNUMBER(G${r}))))`,'耗时次数费用需数字'],
 [`OR(E${r}<0,F${r}<0,G${r}<0)`,'耗时次数费用不能为负']
 ]));
fill(result,'K',6,end('方法结果'),r=>`=IF(A${r}="","",IF(M${r}<>"可用","暂不计分",${pick(`A${r}`,'配对真值','N')}))`);
fill(result,'L',6,end('方法结果'),r=>`=IF(A${r}="","",IF(K${r}<>"可计分","暂不计分",IF(C${r}="待确认","待确认",IF(AND(I${r}="不同",C${r}="合并"),"误合并",IF(AND(I${r}="同一",C${r}="分开"),"漏合并","正确")))))`);

const sum=S['汇总'];sum.showGridLines=false;sum.tabColor='#334860';
fmt(sum,'A1:M28',{font:{name:font,size:11,color:'#243348'},verticalAlignment:'center',rowHeight:27,columnWidth:16});
label(sum,'A2','方向一配对结果汇总');fmt(sum,'A2',{font:{name:font,size:16,bold:true}});
label(sum,'A4','仅统计测试组对象身份；三个方法须使用同一份固定清单。');
label(sum,'A6','已登记测试配对');formula(sum,'C6',`=COUNTIFS(${R('配对真值','M')},"测试",${R('配对真值','A')},"<>")`);
label(sum,'E6','其中可计分配对');formula(sum,'G6',`=COUNTIFS(${R('配对真值','M')},"测试",${R('配对真值','N')},"可计分")`);
label(sum,'I6','需复核或不确定');formula(sum,'K6','=C6-G6');
const summaryHeads=['方法','可计分计划数','有效完成数','待补结果数','自动判定数','误合并数','漏合并数','待确认数','自动判定比例','已判定错误率','进度'];sum.getRange('A9:K9').values=[summaryHeads];fmt(sum,'A9:K9',{fill:'#334860',font:{name:font,size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:48,horizontalAlignment:'center'});fmt(sum,'A10:K12',{fill:'#F0F3F6',rowHeight:34});
for(let r=10;r<=12;r++){
 label(sum,`A${r}`,['A 当前方法','B 简单强基线','C 候选方法'][r-10]);
 formula(sum,`B${r}`,'=$G$6');
 formula(sum,`C${r}`,`=COUNTIFS(${R('方法结果','B')},A${r},${R('方法结果','J')},"测试",${R('方法结果','K')},"可计分")`);
 formula(sum,`D${r}`,`=B${r}-C${r}`);
 formula(sum,`F${r}`,`=COUNTIFS(${R('方法结果','B')},A${r},${R('方法结果','J')},"测试",${R('方法结果','L')},"误合并")`);
 formula(sum,`G${r}`,`=COUNTIFS(${R('方法结果','B')},A${r},${R('方法结果','J')},"测试",${R('方法结果','L')},"漏合并")`);
 formula(sum,`H${r}`,`=COUNTIFS(${R('方法结果','B')},A${r},${R('方法结果','J')},"测试",${R('方法结果','L')},"待确认")`);
 formula(sum,`E${r}`,`=C${r}-H${r}`);
 formula(sum,`I${r}`,`=IF(OR(B${r}=0,D${r}<>0),"",E${r}/B${r})`);
 formula(sum,`J${r}`,`=IF(OR(B${r}=0,D${r}<>0,E${r}=0),"",(F${r}+G${r})/E${r})`);
 formula(sum,`K${r}`,`=IF(B${r}=0,"待录入",IF(D${r}>0,"请补齐结果","已覆盖清单"))`);
}
fmt(sum,'I10:J12',{numberFormat:'0.0%'});fmt(sum,'A1:A28',{columnWidth:22});fmt(sum,'K1:K28',{columnWidth:21});
const notes=[
 ['怎么看','误合并：不同物体被合在一起。漏合并：同一物体被分成两件。'],
 ['自动判定比例','自动给出“合并/分开”的数量 ÷ 可计分测试配对数。'],
 ['已判定错误率','（误合并数＋漏合并数）÷ 自动判定数。需与自动判定比例一起看。'],
 ['缺失结果','尚未填的方法结果不会被当作“正确”或“待确认”。未补齐前不显示比例。'],
 ['无法确定','未复核、完全不可见、真值无法确定或编号冲突的记录不计分，仍保留。'],
 ['怎样比较','先逐个场地看失败案例，再汇总。固定阈值仅用开发组选择，测试组不调参。'],
 ['比例的边界','本表只统计固定配对清单，不能解释为完整App的风险召回率或真实总体错误率。'],
 ['公平性','若方法C更常待确认，要比较相近自动判定比例下的错误率，不能只看错误少。']
];
notes.forEach((a,i)=>{label(sum,`A${15+i}`,a[0]);label(sum,`C${15+i}`,a[1]);});
sum.getRange('D10:D12').conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{fill:'#FFF0D3',font:{color:'#8C4A10'}}});

const guide=S['填写说明'];guide.showGridLines=false;guide.tabColor='#8998A8';fmt(guide,'A1:D48',{font:{name:font,size:11,color:'#243348'},rowHeight:29,verticalAlignment:'center'});fmt(guide,'A1:A48',{columnWidth:23});fmt(guide,'B1:B48',{columnWidth:97});fmt(guide,'C1:D48',{columnWidth:2});label(guide,'A2','方向一采集标注表');fmt(guide,'A2',{font:{name:font,size:16,bold:true}});
const guideRows=[
 ['用途','记录同一物体换角度拍摄后的对应关系，供两周小试使用。先读本页，再从场景登记开始。'],
 ['填写顺序','场景登记 → 照片登记 → 目标标注 → 配对真值 → 方法结果 → 汇总。'],
 ['颜色','浅黄色是输入；浅灰色是自动计算。请保留灰色公式，筛选按钮可查找需补齐的记录。'],
 ['建议数量','3–5个授权空间，每空间2组固定布置，每组8张，共48–80张；是筛查目标，可与导师调整。'],
 ['8种照片','正面、左侧、右侧、近景、远景、部分遮挡、近重复、离开后重访。不要人为制造危险。'],
 ['场地组ID','同一家庭、办公室或同一次可识别的真实场地共用编号。该场地所有房间只进开发组或测试组一边。'],
 ['开发和测试','先划分，再调方法。建议至少保留2个独立场地测试；无法达到时仅报告流程试跑。'],
 ['采集许可','记录允许拍摄的证据位置；这不是统一知情同意模板。是否需要学校审批由导师确认。'],
 ['云端许可','仅允许本地的照片不得上传模型服务。上传前另核对许可、隐私处理与服务条款。'],
 ['照片文件名','使用实际文件名或相对路径，不填居民姓名、住址、电话号码。原图保存在受限资料夹。'],
 ['场景ID','一个房间或明确采集区域一个编号，例如S01。与场地组ID不同。'],
 ['布置组ID','同一组中物体位置不变。换布置、物体移位或关系改变，就新建编号，例如S01G02。'],
 ['观察ID','一张图里的一个对象一个编号，例如O001。一张照片有两根线，就填两行。'],
 ['真实对象ID','同一个实际物体跨角度、跨布置保持同一编号，例如T001。不同物体不能共用编号。'],
 ['问题ID','可选。表示某物体与某区域的一次问题关系。同一物体移到另一通道，对象ID不变、问题ID新建。'],
 ['位置关系','用普通话写参考答案，例如“线缆位于门口通道”。这是人工真值，不直接输入待测方法。'],
 ['框坐标','x1=左边距/图宽，y1=上边距/图高，x2=右边距/图宽，y2=下边距/图高；均为0至1。'],
 ['遮挡目标','部分可见时框住可见部分；完全不可见时框留空，不凭记忆补框，也不将没拍到写成不同物体。'],
 ['标注复核','标注人和复核人使用不同代号。保留分歧；有争议先不计分，由第三人裁决并记依据。'],
 ['配对清单','每空间可先选12对：6对同一、6对不同。覆盖换角度、遮挡、相似干扰和重访；这是待确认目标。'],
 ['配对范围','配对由两个不同照片中的观察组成，研究真实对象身份。问题ID暂不进入本轮主指标。'],
 ['不确定配对','保留“无法确定”，不凑同一/不同数量，不计正式分母。需要补采时记录原因。'],
 ['方法输入','首轮单独检验关联能力。A/B/C共享同样照片和经人工核验的候选框；禁止输入人工对象ID、问题ID、关系真值和配对答案。'],
 ['方法A','当前代码的关联规则；先固定代码版本和模型输出。'],
 ['方法B','简单强基线：只用对象外观相似度进行匹配，阈值仅在开发组选择。'],
 ['方法C','候选：外观加图像中提取的空间关系，并允许待确认。具体规则及阈值在开发组确定。'],
 ['配置版本','用短版本号并另存模型、提示词、代码、参数和阈值。例如A_v1；改配置必须新版本并统一重跑。'],
 ['记录容量','已预留20场景、160照片、400对象观察、120配对和360方法结果；超出前请扩展表与公式范围。'],
 ['示例说明','以下仅演示编号和填写方法，均为虚构，不进入正式数据或汇总。正式输入区目前为空。'],
 ['虚构场景','场地P01；房间S01；布置S01G01；开发组。'],
 ['虚构对象','照片S01G01_01.jpg中的线缆：观察O001、真实对象T001；另一角度观察O002仍是T001。'],
 ['虚构配对','P001对应O001与O002；两位标注者均判断同一。方法输出“分开”时计为漏合并。'],
 ['注意结果含义','这些是身份关联的小试记录，尚无真实结果；不证明检测准确率、事故风险或论文创新。'],
 ['材料依据','温肯科研 05 项目总览，2026-10-29；用户于2026-10-30要求先按方向一准备材料。'],
 ['原始采集元数据','照片登记右侧可填App原始source_id、原始拍摄时间戳（毫秒）和帧序号；缺失时留空，并在元数据说明记录原因。'],
 ['元数据使用边界','方法A依赖真实来源和时间窗。不要补造能让A合并的数值；无法复现A的元数据条件时，单独说明限制。'],
 ['时间戳单位','直接记录App保存的原始时间戳，并确认单位是毫秒；若仅有相对时间或秒级时间，在元数据说明写清来源及转换。']
];
guideRows.forEach((row,i)=>{guide.getRange(`A${5+i}:B${5+i}`).values=[row];});fmt(guide,'A5:A41',{font:{name:font,size:11,bold:true}});fmt(guide,'B5:B41',{wrapText:true,rowHeight:43});
for(const n of ['场景登记','照片登记','目标标注','配对真值','方法结果']){
 const c={场景登记:'M',照片登记:'N',目标标注:'S',配对真值:'O',方法结果:'M'}[n];
 S[n].getRange(`${c}6:${c}${end(n)}`).conditionalFormats.addCustom(`AND(${c}6<>"",${c}6<>"可用")`,{fill:'#FCE9E7',font:{color:'#9C2C22'}});
}

// Disposable in-memory cases verify formula dependencies; all inputs are cleared before export.
const report={cases:[],files:[],sheets:names,capacity:caps};
function expect(v,msg){if(!v)throw new Error(msg);report.cases.push(msg);}
function val(sh,c){return sh.getRange(c).values[0][0];}
const patchOnly=process.argv.includes('--patch-qa');
if(!patchOnly){
scene.getRange('A6:L6').values=[['S01','P01','虚构实验室','办公室','已获许可','仅本地','无隐私','测试','U1',null,'许可记录01','测试后清除']];
photo.getRange('A6:K8').values=[['F01','S01','S01G01','a.jpg',null,'正面','无遮挡','可用','无隐私','使用',''],['F02','S01','S01G01','b.jpg',null,'左侧','无遮挡','可用','无隐私','使用',''],['F03','S01','S01G01','c.jpg',null,'右侧','无遮挡','可用','无隐私','使用','']];
target.getRange('A6:O8').values=[['O01','F01','T01','','线缆','门口','完整可见',0.1,0.1,0.5,0.5,'U1','U2','两人一致',''],['O02','F02','T01','','线缆','门口','完整可见',0.2,0.2,0.6,0.6,'U1','U2','两人一致',''],['O03','F03','T02','','线缆','门口','完整可见',0.3,0.3,0.7,0.7,'U1','U2','两人一致','']];
pair.getRange('A6:J7').values=[['P01','O01','O02','同一','同一','','U1','U2','',''],['P02','O01','O03','不同','不同','','U1','U2','','']];
result.getRange('A6:H7').values=[['P01','A 当前方法','分开','A_v1',1,1,0.1,''],['P02','A 当前方法','合并','A_v1',1,1,0.1,'']];
wb.recalculate();
expect(val(scene,'M6')==='可用','valid scene accepted');expect(val(pair,'N6')==='可计分','reviewed same-object pair eligible');expect(val(result,'L6')==='漏合并','false split classified');expect(val(result,'L7')==='误合并','false merge classified');expect(val(sum,'J10')===1,'two errors out of two decisions = 100%');expect(val(sum,'K11')==='请补齐结果','missing method remains visible');expect(val(sum,'I11')==='','missing method rate blank');
label(result,'C7','待确认');wb.recalculate();expect(val(sum,'I10')===0.5,'abstention lowers auto-decision ratio');expect(val(sum,'J10')===1,'abstention not counted as correct');
result.getRange('A8:H8').values=[['P01','A 当前方法','合并','A_v1',null,null,null,'duplicate']];wb.recalculate();expect(val(result,'M6')==='同配对同方法重复','duplicate results excluded');expect(val(sum,'K10')==='请补齐结果','duplicate results cannot create completion');result.getRange('A8:H8').clear({applyTo:'contents'});
label(pair,'E6','不同');wb.recalculate();expect(val(pair,'N6')==='暂不计分','annotation disagreement excluded');label(pair,'E6','同一');
label(target,'G6','完全不可见');target.getRange('H6:K6').clear({applyTo:'contents'});wb.recalculate();expect(val(pair,'N6')==='暂不计分','invisible target excluded');label(target,'G6','完整可见');target.getRange('H6:K6').values=[[0.1,0.1,0.5,0.5]];
scene.getRange('A7:L7').values=[['S02','P01','虚构房间2','办公室','已获许可','仅本地','无隐私','开发','U1',null,'许可记录01','']];wb.recalculate();expect(val(scene,'M6')==='同场地分组冲突','same location split across development and test rejected');
for(const [n,last] of [['场景登记','L'],['照片登记','K'],['目标标注','O'],['配对真值','J'],['方法结果','H']])S[n].getRange(`A6:${last}${end(n)}`).clear({applyTo:'contents'});
wb.recalculate();expect(val(sum,'K10')==='待录入','empty template remains awaiting data');expect(val(sum,'I10')===''&&val(sum,'J10')==='','empty rates remain blank');
} else {
 scene.getRange('A6:L6').values=[['S01','P01','虚构实验室','办公室','已获许可','仅本地','无隐私','测试','U1',null,'许可记录01','测试后清除']];
 photo.getRange('A6:K6').values=[['F01','S01','S01G01','a.jpg',null,'正面','无遮挡','可用','无隐私','使用','']];
 wb.recalculate();expect(val(photo,'N6')==='可用','missing optional metadata does not block photo record');
 photo.getRange('O6:R6').values=[['original-source-01',1793358000123,12,'虚构验证数据，导出前清除']];
 wb.recalculate();expect(val(photo,'N6')==='可用','numeric timestamp and frame preserve photo eligibility');
 expect(val(photo,'P6')===1793358000123&&val(photo,'Q6')===12,'timestamp and frame stored as numeric values');
 expect(val(guide,'B27').includes('经人工核验的候选框')&&!val(guide,'B27').includes('关系、框或'),'candidate boxes shared while identity truth withheld');
 scene.getRange('A6:L6').clear({applyTo:'contents'});photo.getRange('A6:K6').clear({applyTo:'contents'});photo.getRange('O6:R6').clear({applyTo:'contents'});
 wb.recalculate();expect(val(photo,'N6')==='','all temporary metadata cleared');
 report.reused_unchanged_checks='Original 16 formula tests and unaffected-sheet visual review retained in validation.json.';
}
await fs.mkdir(`${DIR}/workbook-qa`,{recursive:true});
const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'formula error scan',maxChars:3000});report.formula_error_scan=err.ndjson;
await fs.writeFile(`${DIR}/workbook-qa/inspection.ndjson`,(await wb.inspect({kind:'table',range:'汇总!A6:K12',include:'values,formulas',tableMaxRows:8,tableMaxCols:11,maxChars:6000})).ndjson);
const renders=patchOnly?[['填写说明','A23:B41','说明下'],['照片登记','A1:N11','照片'],['照片登记','O1:R11','照片元数据'],['目标标注','A1:K11','目标左']]:[['填写说明','A1:B22','说明上'],['填写说明','A23:B41','说明下'],['汇总','A1:K22','汇总'],['场景登记','A1:M11','场景'],['照片登记','A1:N11','照片'],['照片登记','O1:R11','照片元数据'],['目标标注','A1:K11','目标左'],['目标标注','L1:S11','目标右'],['配对真值','A1:O11','配对'],['方法结果','A1:M11','方法']];
for(const [sheetName,range,file] of renders){const image=await wb.render({sheetName,range,scale:1.6,format:'png'});const path=`${DIR}/workbook-qa/${file}.png`;await fs.writeFile(path,new Uint8Array(await image.arrayBuffer()));report.files.push(path);}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(OUT);report.output=OUT;await fs.writeFile(`${DIR}/workbook-qa/${patchOnly?'patch_validation':'validation'}.json`,JSON.stringify(report,null,2));console.log(JSON.stringify({output:OUT,cases:report.cases.length,formulaErrorScan:report.formula_error_scan,previews:report.files},null,2));
