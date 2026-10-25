"""Browser views: common-timeline playback and direction-selectable signage."""
import html, json, math
from pathlib import Path
from datetime import datetime
from core import ROOMS, values, at, label, wait_label, recommendation, cctv_stamp
from distance_demo import result_series
from distance_display import panel as distance_panel, overlay as distance_overlay, script as distance_script
from distance_stability import result_at
from signage_time import total_time as signage_total, script as signage_time_script


def signage_panel(distance=None, total='측정 불가', element_id='distance-result'):
    shown={**distance,'wait':total} if distance else None
    return distance_panel(shown,element_id=element_id).replace('예상 대기시간:','최종 예상 소요시간:')


def playback_rows(records,cfg,room):
    return [{'t':float(rec['interval_end_s']),**values(rec),'distance':distance}
            for rec,distance in zip(records,result_series(records,cfg,room))]

STYLE='''<style>
*{box-sizing:border-box}body{margin:0;background:#f1f6fa;color:#14212d;font-family:system-ui,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif}button{cursor:pointer;border:0;border-radius:8px;background:#0667e8;color:white;padding:11px 18px;font-weight:750}button.secondary{background:#edf3f8;color:#536579}.bar{display:flex;align-items:center;gap:12px;background:white;border:1px solid #e6edf4;border-radius:14px;padding:14px 18px;margin-bottom:20px}.bar input{flex:1;accent-color:#0868eb}.pill{font-size:11px;border-radius:5px;padding:4px 7px;background:#edf5ff;color:#1265c5}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{border:1px solid #e2eaf2;background:white;border-radius:15px;overflow:hidden}.cardhead{padding:17px;display:flex;justify-content:space-between;align-items:center;font-size:14px;font-weight:750}.video{background:#142332;aspect-ratio:16/9;position:relative}.video video{width:100%;height:100%;object-fit:contain}.video .empty{height:100%;display:flex;align-items:center;justify-content:center;color:#b2c0cd;font-size:13px}.metrics{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:20px 8px}.small{color:#8694a3;font-size:11px;font-weight:650}.big{font-size:26px;font-weight:800;letter-spacing:-1px;margin-top:5px}.unit{font-size:12px;font-weight:600;color:#8392a2;margin-left:4px}.foot{padding:12px 18px;border-top:1px solid #edf1f6;display:flex;justify-content:space-between;font-size:11px;color:#8493a2}.notice{font-size:12px;color:#7b8d9e;line-height:1.7;margin-top:14px}.statline{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px}.statline>div{background:white;padding:18px;border:1px solid #e4ecf3;border-radius:13px}.statline strong{font-size:26px;display:block;margin-top:8px}.sg-head{display:flex;justify-content:space-between;align-items:flex-start;padding:24px 6px}.sg-head h1{font-size:36px;letter-spacing:-2px;margin:5px 0 10px}.sg-head p{font-size:12px;color:#8193a4}.sg-layout{display:grid;grid-template-columns:3fr 1fr;gap:14px}.map{background:white;border-radius:22px;overflow:hidden;min-height:500px}.sg-side{padding:22px;background:white;border-radius:22px}.sg-side h2{font-size:23px;margin:5px 0 22px}.sg-item{border-radius:16px;padding:18px;margin-bottom:16px;background:#f2f5f8}.sg-item h3{font-size:13px;margin:0 0 8px}.sg-item .minutes{font-size:60px;font-weight:850;letter-spacing:-3px;line-height:1.25}.sg-item .minutes span{font-size:18px;letter-spacing:0}.sg-item footer{padding-top:10px;border-top:1px solid #d9e5e8;margin-top:10px;font-size:11px;font-weight:650}.green{background:#e1f5ee;color:#00846c}.yellow{background:#fff2ce;color:#965d00}.red{background:#fff1ef;color:#d6403d}.gray{background:#f3f5f7;color:#88939d}.badge{display:inline-block;font-size:10px;background:#00846c;color:white;border-radius:20px;padding:4px 8px;float:right}.sg-note{font-size:11px;color:#8a9baa;line-height:1.7;padding:10px}.date{text-align:right;color:#738290;font-size:13px}.date strong{font-size:32px;color:#152331;display:block}.alert{color:#c24842;font-size:12px}.fullscreen{background:#dde9f5;color:#31649a;padding:8px 12px}.row{display:flex;justify-content:space-between;align-items:center}
.cctv-tag,.cctv-clock{position:absolute;top:10px;padding:5px 8px;background:#14212dbb;color:white;font-size:11px;border-radius:4px;font-variant-numeric:tabular-nums}.cctv-tag{left:10px}.cctv-clock{right:10px;font-weight:750}.detail-video{aspect-ratio:16/9;max-height:510px;background:#122230;position:relative;border-radius:14px;overflow:hidden}.detail-video video{width:100%;height:100%;object-fit:contain}.detail-video .cctv-clock{font-size:18px}.detail-video .cctv-tag{font-size:13px}.detail-info{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}.detail-info>div{background:white;border:1px solid #e4ecf3;border-radius:12px;padding:16px}.detail-info strong{display:block;font-size:28px;margin-top:8px}.detail-info .small{font-size:12px}.statepill{font-weight:800;font-size:13px;border-radius:20px;padding:5px 12px;background:#e1f5ee;color:#00846c}.detail-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;font-size:16px;font-weight:750}
@media(max-width:800px){.cards{grid-template-columns:1fr}.sg-layout{grid-template-columns:1fr}.sg-head h1{font-size:28px}.statline{gap:7px}.statline>div{padding:10px}.card video{max-height:300px}.sg-side{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.sg-side h2,.sg-side>.small{grid-column:1/-1}.sg-item{padding:10px}.sg-item .minutes{font-size:34px}.sg-item h3{font-size:11px}.map{min-height:300px}}

body{font-size:12px}button{font-size:11px;padding:8px 11px}.bar{padding:9px 12px;gap:8px;margin-bottom:12px;border-radius:10px}.cards{gap:10px}.cardhead{padding:11px 12px;font-size:12px}.metrics{padding:12px;gap:12px 8px}.big{font-size:20px;margin-top:3px}.foot{padding:8px 12px;font-size:10px}.small{font-size:10px}.notice{font-size:10px;line-height:1.45;margin-top:7px}.statline{gap:10px;margin-bottom:12px}.statline>div{padding:11px 13px}.statline strong{font-size:21px;margin-top:4px}
.detail-shell{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:12px}.detail-video{height:245px;max-height:245px;aspect-ratio:auto;border-radius:10px}.detail-info{grid-template-columns:1fr 1fr;gap:8px;margin-top:0;align-content:start}.detail-info>div{padding:12px 9px;border-radius:9px}.detail-info strong{font-size:20px;margin-top:6px;letter-spacing:-.5px}.detail-info .small{font-size:10px}.detail-head{font-size:13px;margin-bottom:8px}.detail-video .cctv-clock{font-size:14px}.detail-video .cctv-tag{font-size:10px}.statepill{font-size:11px;padding:4px 10px}
.sg-head{padding:6px 4px 10px}.sg-head h1{font-size:23px;letter-spacing:-1px;margin:4px 0 5px}.sg-head p{font-size:10px;margin:0}.date{font-size:10px}.date strong{font-size:22px}.sg-layout{grid-template-columns:minmax(0,3fr) minmax(190px,1fr);gap:10px}.map{min-height:0;border-radius:14px;display:flex;align-items:center;justify-content:center}.map svg{width:100%;max-height:360px}.sg-side{padding:12px;border-radius:14px}.sg-side h2{font-size:16px;margin:3px 0 10px}.sg-item{padding:10px 12px;margin-bottom:8px;border-radius:10px}.sg-item h3{font-size:11px;margin-bottom:5px}.sg-item .minutes{font-size:34px;letter-spacing:-1.5px;line-height:1.2}.sg-item .minutes span{font-size:14px}.sg-item footer{margin-top:5px;padding-top:6px;font-size:10px}.sg-note{font-size:9px;padding:6px}.badge{font-size:9px;padding:3px 7px}.previews{margin:0 0 8px;color:#7a8b9c;font-size:10px}.preview-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:7px}.preview-grid video{width:100%;height:90px;object-fit:contain;background:#142332;border-radius:6px}.preview-grid small{font-size:10px}
@media(max-width:700px){.detail-shell{grid-template-columns:1fr}.detail-video{height:220px}.detail-info{grid-template-columns:repeat(4,1fr)}.sg-layout{grid-template-columns:1fr}.sg-side{display:block}.map svg{max-height:300px}.cards{grid-template-columns:repeat(3,1fr)}.metrics{grid-template-columns:1fr;gap:8px}.big{font-size:17px}.sg-head h1{font-size:20px}}
.video{height:150px;aspect-ratio:auto}.metrics{padding:10px;gap:8px}.big{font-size:18px}.detail-video{height:210px;max-height:210px}

/* Preserve the complete source frame and let the page grow with it. */
.video{height:auto;aspect-ratio:auto}.video video{display:block;width:100%;height:auto;max-height:none;object-fit:contain}.video .empty{min-height:180px}
.detail-head{margin-bottom:12px;font-size:15px}.detail-head-actions{display:flex;align-items:center;gap:8px}
.detail-shell{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:18px;align-items:start}
.detail-video{width:100%;height:auto;max-height:none;aspect-ratio:auto;background:#edf3f8;border-radius:12px;align-self:start}
.detail-video video{display:block;width:100%;height:auto;max-height:none;object-fit:contain}
.detail-info{display:grid;grid-template-columns:1fr;gap:10px;margin:0;align-content:start}
.detail-info>div{padding:18px 14px;min-height:88px;border-radius:12px;background:#fff;border:1px solid #dde7f0;box-shadow:0 2px 8px #19395406}
.detail-info strong{font-size:25px;margin-top:8px;line-height:1.25;letter-spacing:-.5px;overflow-wrap:anywhere}
.detail-info .small{font-size:11px;line-height:1.5}.detail-head .statepill{padding:5px 12px}
@media(max-width:800px){.detail-shell{grid-template-columns:minmax(0,1fr) 220px;gap:12px}.detail-info{gap:8px}.detail-info>div{padding:14px 10px;min-height:100px}.detail-info strong{font-size:22px}.detail-info .small{font-size:10px}}
@media(max-width:600px){.detail-shell{grid-template-columns:1fr}.detail-info{grid-template-columns:1fr}.detail-video{height:auto;max-height:none}.detail-video .empty{padding:70px 16px!important}}
/* Current congestion summary above the four compact data rows. */
.detail-shell{grid-template-columns:minmax(0,1fr) 270px}.detail-side{display:grid;gap:12px;min-width:0}
.detail-congestion{padding:18px;border-radius:14px;background:#edf2f6;color:#7a8b9b;line-height:1.4}
.detail-congestion h3{font-size:13px;margin:0 0 7px}.detail-congestion .congestion-state{font-size:12px;font-weight:750}
.detail-congestion .congestion-wait{font-size:40px;font-weight:850;letter-spacing:-1.5px;margin:7px 0 12px;line-height:1.2}
.detail-congestion .congestion-wait small{font-size:17px;letter-spacing:0;margin-left:3px}
.detail-congestion footer{padding-top:10px;border-top:1px solid currentColor;font-size:11px;font-weight:650}
.detail-info{display:grid;grid-template-columns:1fr!important;gap:0;padding:0 14px;background:white;border:1px solid #e1eaf2;border-radius:12px}
.detail-info>div{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 0;min-height:0;border:0;border-bottom:1px solid #edf1f5;border-radius:0;box-shadow:none;background:transparent}
.detail-info>div:last-child{border-bottom:0}.detail-info .small{font-size:11px}.detail-info strong{font-size:18px;line-height:1.4;margin:0;white-space:nowrap;letter-spacing:-.4px}
@media(max-width:800px){.detail-shell{grid-template-columns:minmax(0,1fr) 230px}}
@media(max-width:600px){.detail-shell{grid-template-columns:1fr}}

/* High contrast congestion labels, including compact dashboard card footers. */
.congestion-badge{display:inline-flex;align-items:center;justify-content:center;min-width:76px;min-height:34px;padding:6px 16px;border-radius:9px;font-size:15px;font-weight:850;line-height:1.35;border:1px solid transparent;letter-spacing:.2px;white-space:nowrap}
.congestion-badge[data-state="여유"]{color:#276b58;background:#e3f2eb;border-color:#cce5d8}
.congestion-badge[data-state="보통"]{color:#806122;background:#faf0d8;border-color:#eddfb8}
.congestion-badge[data-state="매우 혼잡"]{color:#8e1b40;background:#f7dce6;border-color:#dca1b7}
.congestion-badge[data-state="측정 불가"]{color:#536579;background:#edf2f6;border-color:#c7d4df}
.congestion-badge[data-state="혼잡"]{color:#a24850;background:#f9e7e9;border-color:#efced3}
.congestion-badge[data-state="미측정"]{color:#536579;background:#edf2f6;border-color:#c7d4df}
.foot{padding:10px 12px;gap:12px}.foot>span:last-child{font-size:11px}
.statepill{font-size:15px!important;font-weight:850;padding:7px 16px!important}
.detail-congestion .congestion-state{font-size:18px;font-weight:850}
.sg-item>div:not(.minutes){font-size:16px!important;font-weight:850!important}
.bar button{min-height:36px}.bar button:disabled{cursor:default;opacity:.65}.bar .pause-button{background:#f2f6fa;color:#536579;border:0}
</style>'''

def json_js(x):return json.dumps(x,ensure_ascii=False).replace('</','<\\/')

def playback_source():return (Path(__file__).resolve().parent/'playback.js').read_text(encoding='utf-8')

def dashboard(records,urls,cfg):
    series={r:playback_rows(records[r],cfg,r) for r in ROOMS}
    chunks=[]
    for i,(r,name) in enumerate(ROOMS.items(),1):
        video=f'<video id="v-{r}" controls muted playsinline preload="metadata" src="{html.escape(urls[r],quote=True)}"></video>' if urls.get(r) else '<div class="empty">시연 설정에서 영상을 연결하세요</div>'
        chunks.append(f'''<div class="card"><div class="cardhead">{name} 화장실 <span class="pill">CAM 0{i}</span></div><div class="video">{video}{distance_overlay(cfg,r)}<span class="cctv-tag">● CCTV · {name}</span><span class="cctv-clock" id="{r}-clock">14:00:00</span></div><div class="metrics"><div><div class="small">외부 대기 인원</div><div class="big" id="{r}-outside">—</div></div><div><div class="small">예상 대기시간</div><div class="big" id="{r}-wait">측정 불가</div></div><div><div class="small">내부 잔류 인원 · 추정</div><div class="big" id="{r}-inside">—</div></div><div><div class="small">전체 대기 인원 · 추정</div><div class="big" id="{r}-queue">—</div></div></div><div class="foot"><span class="congestion-badge" data-state="측정 불가" id="{r}-status">측정 불가</span><span id="{r}-time">기록 없음</span></div><div class="alert" id="{r}-error"></div>{distance_panel(element_id="distance-"+r)}</div>''')
    return STYLE+'''<div class="bar"><button type="button" id="play">▶ 동시 재생</button><button type="button" class="pause-button" id="pause">Ⅱ 일시정지</button><button class="secondary" id="reset">처음부터</button><input id="seek" aria-label="공통 영상 시점" type="range" min="0" max="1" step="0.1" value="0"><span id="time" style="font-size:12px;min-width:150px">14:00:00 / 14:00:00</span></div><div class="alert" id="playback-error" role="status"></div><div class="statline"><div><span class="small">모니터링 화장실</span><strong>3 <span class="unit">곳</span></strong></div><div><span class="small">동일 시점 전체 대기 · 추정</span><strong id="total">—</strong></div><div><span class="small">혼잡 화장실</span><strong id="busy">—</strong></div></div><div class="cards">'''+''.join(chunks)+'''</div><section class="train-alert-panel" style="margin-top:18px;padding:20px;background:white;border:1px solid #e2eaf2;border-radius:14px"><h2 style="margin:0 0 10px;font-size:18px">도착·출발 예정 열차 알림</h2><div id="train-alert-caption" class="notice"></div><div id="train-alert-message" role="status" style="margin:12px 0;color:#677f93"></div><table id="train-alert-table" style="width:100%;text-align:left;border-collapse:collapse;font-size:13px"><thead><tr><th>예정일시</th><th>열차번호</th><th>열차종류</th><th>운행구분</th></tr></thead><tbody id="train-alert-rows"></tbody></table></section><div class="notice">CCTV 시연 영상 · 14:00:00 시작 / YOLO11n + ByteTrack 분석 결과 / 재생 시각에 저장된 기록을 연결합니다. 분석 전·기록 범위 밖은 미측정으로 표시합니다.<br>세 영상을 순차 분석한 뒤 동시 재생해 비교합니다. 내부 인원은 분석 모듈의 추정값입니다. 예상 대기시간·혼잡도는 임의 거리 기준 시연값입니다.</div>'''+f'''<script>
{playback_source()}
{distance_script()}
const data={json_js(series)}, cfg={json_js(cfg)}, rooms=Object.keys(data), vs=rooms.map(r=>document.getElementById('v-'+r)).filter(Boolean);
let t=0,end=0;
const seek=document.getElementById('seek'),btn=document.getElementById('play');
const fmt=s=>String(Math.floor(s/60)).padStart(2,'0')+':'+String(Math.floor(s%60)).padStart(2,'0');
const clock=s=>new Date((14*3600+Math.floor(s))*1000).toISOString().slice(11,19);
const field=(r,k,x)=>document.getElementById(r+'-'+k).textContent=x;
function render(){{
  let sum=0,known=0,busy=0,distanceKnown=0;
  rooms.forEach(r=>{{let a=data[r].filter(x=>x.t<=t+0.001), rec=a.length?a[a.length-1]:null;
    if(rec && t>data[r][data[r].length-1].t+1.1) rec=null;
    const d=distanceAt(data[r],t);
    paintDistance(document.getElementById('distance-'+r),d,document.getElementById('distance-overlay-'+r));
    ['outside','inside','queue'].forEach(k=>field(r,k,rec&&rec[k]!=null?rec[k]+' 명':'—'));
    field(r,'wait',d.wait);
    let q=rec?.queue, name=d.status;
    if(d.reached_m!=null){{distanceKnown++;if(d.reached_m>=10)busy++;}}
    field(r,'status',name);document.getElementById(r+'-status').dataset.state=name;
    field(r,'clock',clock(t));
    field(r,'time',rec?'CCTV '+clock(rec.t)+' 기준':'이 시점의 기록 없음');
    if(q!=null){{sum+=q;known++;}}
  }});
  document.getElementById('total').textContent=known===3?sum+' 명':'미측정';document.getElementById('busy').textContent=distanceKnown===3?busy+' 곳':'측정 불가';
  seek.value=t;document.getElementById('time').textContent=clock(t)+' / '+clock(end);
  renderTrainAlerts(t);
}}
let lastTrainSecond=-1;
function trainEventLabel(row,seconds){{
 const remaining=Math.max(0,Math.ceil(row.offset_s-seconds)),minutes=Math.floor(remaining/60),secs=remaining%60;
 const duration=minutes?(secs?minutes+'분 '+secs+'초':minutes+'분'):secs+'초';
 return seconds>=row.offset_s?row.event:row.event+'예정 ('+duration+' 남음)';
}}
function renderTrainAlerts(seconds){{
 const second=Math.floor(seconds);if(second===lastTrainSecond)return;lastTrainSecond=second;
 const stamp=new Date((cfg.capture_date||'2026-10-14')+'T14:00:00Z');stamp.setUTCSeconds(stamp.getUTCSeconds()+second);
 document.getElementById('train-alert-caption').textContent='영상 재생 기준 '+stamp.toISOString().slice(0,19).replace('T',' ')+'부터 20분 · 예정 시각 경과 후 1분간 표시 · MySQL 예정 시간표';
 const body=document.getElementById('train-alert-rows'),table=document.getElementById('train-alert-table'),message=document.getElementById('train-alert-message');
 body.replaceChildren();
 if(cfg.train_db_status!=='connected'){{table.hidden=true;message.textContent=cfg.train_db_message||'열차 정보 탭에서 MySQL 연결을 설정해주세요.';return;}}
 const upcoming=(cfg.train_events||[]).filter(row=>row.offset_s>seconds-60&&row.offset_s<=seconds+1200).sort((a,b)=>a.offset_s-b.offset_s).slice(0,5);
 table.hidden=!upcoming.length;
 message.textContent=upcoming.length?'':cfg.train_day_available?'최근 1분 및 앞으로 20분 이내 도착·출발 열차가 없습니다.':'영상 기준일의 열차 기록이 DB에 없습니다. railway_system_v5에서 해당 날짜를 생성·저장해주세요.';
 for(const row of upcoming){{const tr=document.createElement('tr');for(const [index,value] of [row.day+' '+row.time,row.number,row.kind,trainEventLabel(row,seconds)].entries()){{const td=document.createElement('td');td.textContent=value;if(index===3){{td.style.color=seconds>=row.offset_s?'#087f5b':row.event==='출발'?'#b66b00':'#0867df';td.style.fontWeight='750';}}td.style.padding='10px 4px';td.style.borderTop='1px solid #e5edf4';tr.appendChild(td);}}body.appendChild(tr);}}
}}
const player=createPlayback({{videos:vs,expectedVideos:3,key:cfg.playback_key||'default',limit:cfg.playback_end,fallbackEnd:Math.max(0,...rooms.map(r=>data[r].length?data[r][data[r].length-1].t:0)),onTime:(s,d)=>{{t=s;end=d;seek.max=end||1;render();}},onState:playing=>{{btn.disabled=playing;btn.setAttribute('aria-pressed',String(playing));}},onError:message=>{{document.getElementById('playback-error').textContent=message;}},onVideoError:(video,message)=>{{const r=rooms.find(r=>document.getElementById('v-'+r)===video);if(r)field(r,'error',message);}}}});
btn.onclick=()=>{{document.getElementById('playback-error').textContent='';rooms.forEach(r=>field(r,'error',''));player.play();}};document.getElementById('pause').onclick=()=>player.pause();seek.oninput=()=>player.seek(Number(seek.value));document.getElementById('reset').onclick=()=>player.reset();
</script>'''

def floor_map(current,vals,cfg,best):
    pos={'north':(600,160),'east':(950,440),'south':(160,500)}
    nums={'south':1,'north':2,'east':3}
    svg=['''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1060 680" role="img" aria-label="부산역 화장실 안내 개념도"><rect width="1060" height="680" fill="white"/><g fill="#c2c8cf" stroke="white" stroke-width="3"><rect x="60" y="90" width="100" height="48"/><rect x="165" y="90" width="25" height="48"/><rect x="195" y="90" width="50" height="48"/><rect x="250" y="90" width="50" height="48"/><rect x="305" y="90" width="50" height="48"/><rect x="475" y="90" width="70" height="48"/><rect x="550" y="90" width="100" height="120" fill="#e9edf1"/><rect x="720" y="90" width="310" height="260"/><rect x="520" y="270" width="35" height="100"/><rect x="465" y="270" width="30" height="115"/><rect x="520" y="375" width="115" height="34" fill="#7fb5ff"/><rect x="640" y="375" width="100" height="34"/><rect x="745" y="375" width="130" height="34"/><rect x="880" y="375" width="150" height="34"/><path d="M110 510 Q450 620 1030 505 L1030 555 Q460 675 150 565Z"/><rect x="70" y="140" width="85" height="25"/><rect x="70" y="169" width="85" height="20"/><rect x="350" y="460" width="35" height="35"/><rect x="390" y="460" width="35" height="35"/><rect x="630" y="460" width="35" height="35"/><rect x="420" y="510" width="40" height="50"/></g><g fill="none" stroke="#545f6b" stroke-width="10"><path d="M55 115V83H410 M470 83H715 M80 190V150 M80 230V285L100 315V355 M80 440L160 520 Q450 650 1035 555"/></g><g font-family="system-ui,sans-serif" fill="#17212d" font-weight="750"><text x="425" y="60" font-size="27" text-anchor="middle">9번 출구</text><text x="450" y="650" font-size="27" text-anchor="middle">7번 출구</text><text x="100" y="410" font-size="25" text-anchor="middle">8번 출구</text><text x="875" y="235" font-size="40" text-anchor="middle">바다맞이방</text><text x="575" y="398" font-size="17" text-anchor="middle">매표창구</text><circle cx="315" cy="265" r="22" fill="#0667e8"/><text x="315" y="275" font-size="30" font-style="italic" fill="white" text-anchor="middle">i</text><text x="315" y="310" font-size="16" text-anchor="middle">종합안내</text><text x="145" y="218" font-size="17">← 타는 곳</text><text x="625" y="238" font-size="17">타는 곳 →</text><text x="760" y="465" font-size="17">↑ 타는 곳</text></g>''']
    x,y=pos[current]
    target=pos[best] if best else (x,y)
    route=f'M{x} {y} L400 {y} L400 435 L{target[0]} 435 L{target[0]} {target[1]}'
    svg.append(f'<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#0874ec"/></marker></defs><path id="sign-route" d="{route}" style="display:{"block" if best else "none"}" fill="none" stroke="#0874ec" stroke-width="7" stroke-dasharray="10 9" marker-end="url(#arrow)" opacity=".8"/>')
    for r,(x,y) in pos.items():
        status,color=label(vals[r],cfg)
        tag_y=y-114 if r!='south' else y+36
        bx=min(850,max(20,x-55))
        svg.append(f'<circle cx="{x}" cy="{y}" r="31" id="ring-{r}" fill="white" stroke="{color}" stroke-width="3"/><circle cx="{x}" cy="{y}" r="25" id="dot-{r}" fill="{color}"/><text x="{x}" y="{y+10}" text-anchor="middle" fill="white" font-family="system-ui" font-size="30" font-weight="800">{nums[r]}</text><rect x="{bx}" y="{tag_y}" width="200" height="81" rx="12" id="tag-{r}" fill="{color}"/><text x="{bx+13}" y="{tag_y+22}" fill="white" font-family="system-ui" font-size="12" font-weight="650">{nums[r]}번 · {ROOMS[r]} 화장실</text><text x="{bx+13}" y="{tag_y+46}" fill="white" font-family="system-ui" font-size="20" font-weight="800" id="map-status-{r}">{status}</text><text x="{bx+13}" y="{tag_y+68}" text-anchor="start" fill="white" font-family="system-ui" font-size="17" font-weight="750" id="map-wait-{r}">{vals[r]["total_time"]}</text>')
        if r==current:svg.append(f'<rect x="{x-52}" y="{y-48}" width="104" height="23" rx="12" fill="#1554ed"/><text x="{x}" y="{y-32}" text-anchor="middle" font-family="system-ui" font-size="12" font-weight="700" fill="white">현재 위치</text>')
    svg.append('<text x="35" y="673" font-size="10" fill="#8a98a6" font-family="system-ui">제공 시안 기반 개념도 · 경로는 안내용이며 실제 보행 경로 검증이 필요합니다.</text></svg>')
    return ''.join(svg)

SIGNAGE_FILL_STYLE = '<style id="signage-fill-screen">\n.sg-head{padding:10px 4px 16px}.sg-head h1{font-size:clamp(26px,2.4vw,42px);margin:5px 0 8px}.sg-head p{font-size:13px}.sg-head .small{font-size:13px}.date{font-size:13px}.date strong{font-size:clamp(26px,2.3vw,38px)}\n.sg-layout{grid-template-columns:minmax(0,3fr) minmax(300px,1fr);gap:16px;align-items:stretch}\n.map{min-width:0;min-height:0;border-radius:18px;padding:10px;display:flex;align-items:center;justify-content:center}\n.map svg{display:block;width:100%;height:auto;max-height:none;aspect-ratio:1060/680;flex:0 1 auto}\n.sg-side{display:flex;flex-direction:column;min-width:0;padding:18px;border-radius:18px}.sg-side>.small{font-size:13px}.sg-side h2{font-size:22px;margin:6px 0 14px}\n#sign-items{display:grid;grid-template-rows:repeat(3,minmax(min-content,1fr));gap:12px;flex:1}\n.sg-item{margin:0;padding:16px;border-radius:14px;min-width:0}.sg-item h3{font-size:15px;margin:0 0 8px}.sg-item .minutes{font-size:clamp(40px,3.4vw,64px);line-height:1.15;margin:8px 0;letter-spacing:-2px}.sg-item .minutes span{font-size:19px}.sg-item footer{font-size:12px;line-height:1.5;padding-top:9px;margin-top:8px}.sg-item .badge{font-size:11px}.sg-note{font-size:11px;line-height:1.6;padding:10px 4px}\n@media(max-width:1000px){.sg-layout{grid-template-columns:minmax(0,2fr) minmax(260px,1fr)}.sg-side{padding:14px}.sg-item{padding:12px}.sg-item .minutes{font-size:40px}}\n@media(max-width:700px){.sg-layout{grid-template-columns:1fr}.sg-side{display:flex}.map svg{max-height:none}#sign-items{grid-template-rows:none;grid-template-columns:1fr}.sg-head h1{font-size:25px}.sg-head p{font-size:11px}.date strong{font-size:24px}}\n</style>'
def signage(records,current,t,cfg):
    recs={r:at(records[r],t) if records[r] and t<=float(records[r][-1]['interval_end_s'])+1.1 else None for r in ROOMS}
    vals={}
    for r in ROOMS:
        vals[r]={**values(recs[r]),'distance':result_at(records[r],result_series(records[r],cfg,r),t)}
        vals[r]['total_time']=signage_total(vals[r]['distance'],cfg.get('walk',{}).get(current,{}).get(r))
    best=recommendation(current,vals,cfg)
    nums={'south':1,'north':2,'east':3}
    dt=cctv_stamp(t,cfg);date=dt.strftime('%Y.%m.%d');clock=dt.strftime('%H:%M:%S')
    order=[current]+sorted([r for r in ROOMS if r!=current],key=lambda r:(vals[r]['distance']['reached_m'] if vals[r]['distance']['reached_m'] is not None else float('inf'),cfg['walk'][current][r]))
    panels=[]
    for r in order:
        status,color=label(vals[r],cfg);distance=vals[r]['distance']
        cls='red' if status in ('혼잡','매우 혼잡') else 'yellow' if status=='보통' else 'green' if status=='여유' else 'gray'
        badge='<span class="badge">혼잡 단계 낮음</span>' if r==best else ''
        total=vals[r]['total_time']
        panels.append(f'<div class="sg-item {cls}">{badge}<h3>{nums[r]}번 · {ROOMS[r]} 화장실</h3><div id="sign-state-{r}">{status}</div><div class="minutes" id="sign-wait-{r}">{total}</div><footer>최종 예상 소요시간 · 임의 거리 기준 시연값</footer>{signage_panel(distance,total,element_id="distance-sign-"+r)}</div>')
    return STYLE+SIGNAGE_FILL_STYLE+f'''<div class="sg-head"><div><div class="small" style="color:#0068e9">● 역내 편의시설 안내 / RESTROOM GUIDE</div><h1>화장실 혼잡도 안내</h1><p>도보 이동을 포함한 최종 예상 소요시간·혼잡도는 임의 거리 기준 시연값입니다.</p></div><div class="date">{date}<strong id="sign-clock">{clock}</strong><span class="pill">시연 · 영상 {t:.1f}초</span></div></div><div class="sg-layout"><div class="map">{floor_map(current,vals,cfg,best)}</div><div class="sg-side"><div class="small" style="color:#0068e9">TOILET STATUS</div><h2>화장실 이용 안내</h2><div id="sign-items">{''.join(panels)}</div></div></div><div class="sg-note">임의 거리 기준 시연값 · 최종 예상 소요시간은 도보 이동을 포함한 시연용 범위입니다. 거리 혼잡 단계가 낮은 곳을 안내하며 동일 단계는 도보시간으로 정렬합니다. 정확한 실제 소요시간이나 가장 빠른 도착을 보장하지 않습니다. 측정 불가가 있으면 추천하지 않습니다.</div>'''


def detail_video(room,records,url,cfg,start=0.):
    series=playback_rows(records,cfg,room)
    video=f'<video id="detail-video" controls muted playsinline preload="metadata" src="{html.escape(url,quote=True)}"></video>' if url else '<div class="empty" style="padding:120px;text-align:center;color:white">영상 파일을 찾지 못했습니다. 메인 상단에서 연결을 확인하세요.</div>'
    fields=''.join(f'<div><span class="small">{title}</span><strong id="detail-{key}">미측정</strong></div>' for key,title in [('outside','외부 대기 인원'),('inside','내부 잔류 · 추정'),('queue','전체 대기 · 추정'),('wait','예상 대기시간')])
    return STYLE+f'''<div class="detail-head"><span>{ROOMS[room]} 화장실 CCTV</span><span class="detail-head-actions"><span class="statepill" id="detail-status">측정 불가</span></span></div><div class="detail-shell"><div class="detail-video" id="detail-stage">{video}{distance_overlay(cfg,room)}<span class="cctv-tag">● CCTV · {ROOMS[room]} 화장실</span><span class="cctv-clock" id="detail-clock">14:00:00</span></div><aside class="detail-side"><section class="detail-congestion" id="detail-congestion"><h3>{ROOMS[room]} 화장실</h3><div class="congestion-state" id="detail-congestion-state">현재 혼잡도 · 측정 불가</div><div class="congestion-wait" id="detail-congestion-wait">측정 불가</div><footer id="detail-congestion-note">이 시점의 분석 기록 없음</footer></section><div class="detail-info">{fields}</div>{distance_panel(element_id="distance-detail")}</aside></div><div class="notice" id="detail-note">14:00:00 시작 · 재생 시점에 해당하는 모델 분석 기록</div><script>
{playback_source()}
{distance_script()}
const rows={json_js(series)},cfg={json_js(cfg)},start={float(start)};
const video=document.getElementById('detail-video');
function clock(s){{return new Date((14*3600+Math.floor(s))*1000).toISOString().slice(11,19);}}
function update(t){{
 const records=rows.filter(r=>r.t<=t+.001);let rec=records.length?records[records.length-1]:null;
 if(rec&&t>rows[rows.length-1].t+1.1)rec=null;
 const d=distanceAt(rows,t);
 paintDistance(document.getElementById('distance-detail'),d,document.getElementById('distance-overlay-{room}'));
 document.getElementById('detail-clock').textContent=clock(t);
 ['outside','inside','queue'].forEach(k=>document.getElementById('detail-'+k).textContent=rec&&rec[k]!=null?rec[k]+'명':'미측정');
 document.getElementById('detail-wait').textContent=d.wait;
 const [state,color,cls]=distanceState({{distance:d}});
 const pill=document.getElementById('detail-status');pill.textContent=state;pill.style.color=color;pill.style.background=cls==='gray'?'#edf2f6':cls==='red'?'#fff0ef':cls==='yellow'?'#fff3cd':'#e1f5ee';
 const card=document.getElementById('detail-congestion');card.style.color=color;card.style.background=pill.style.background;
 document.getElementById('detail-congestion-state').textContent='현재 혼잡도 · '+state;
 document.getElementById('detail-congestion-wait').textContent=d.wait;
 document.getElementById('detail-congestion-note').textContent='임의 거리 기준 시연값 · '+d.reason;
 document.getElementById('detail-note').textContent=(rec?'CCTV '+clock(rec.t)+' 분석 기록 기준':'이 시점의 분석 기록이 없습니다.')+' · 예상 대기시간·혼잡도는 임의 거리 기준 시연값';
}}
createPlayback({{videos:video?[video]:[],key:cfg.playback_key||'default',limit:cfg.playback_end,fallbackEnd:rows.length?rows[rows.length-1].t:0,onTime:update,onError:message=>document.getElementById('detail-note').textContent=message}});
</script>'''


def live_signage(records,current,urls,cfg):
    series={r:playback_rows(records[r],cfg,r) for r in ROOMS}
    previews=[]
    for r in ROOMS:
        clip=f'<video id="sign-video-{r}" muted playsinline preload="metadata" src="{html.escape(urls[r],quote=True)}"></video>' if urls.get(r) else '<div>영상 없음</div>'
        previews.append(f'<div>{clip}<small>{ROOMS[r]} CCTV</small></div>')
    controls='<div class="bar"><button type="button" id="sign-play">▶ 재생</button><button type="button" class="pause-button" id="sign-pause">Ⅱ 일시정지</button><button class="secondary" id="sign-reset">처음부터</button><input id="sign-seek" aria-label="CCTV 공통 재생 시점" type="range" min="0" max="1" step="0.1" value="0"><span id="sign-timeline" style="min-width:142px;font-size:11px">14:00:00</span></div>'
    controls+='<details class="previews"><summary>CCTV 재생 화면 펼치기</summary><div class="preview-grid">'+''.join(previews)+'</div></details><div class="alert" id="sign-error"></div>'
    body=signage(records,current,0,cfg)
    close=body.index('</style>')+len('</style>')
    body=body[:close]+controls+body[close:]
    body=body.replace('<span class="pill">시연 · 영상 0.0초</span>','<span class="pill" id="sign-position">CCTV 재생 연동</span>')
    body=body.replace('<div class="sg-note">','<div class="sg-note" id="sign-note">')
    return body+f'''<script>
{playback_source()}
{distance_script()}
{signage_time_script()}
const rows={json_js(series)},cfg={json_js(cfg)},current={json_js(current)},roomNames={json_js(ROOMS)};
const rooms=Object.keys(rows), nums={{south:1,north:2,east:3}},pos={{north:[600,160],east:[950,440],south:[160,500]}};
const videos=rooms.map(r=>document.getElementById('sign-video-'+r)).filter(Boolean);
const seek=document.getElementById('sign-seek'),button=document.getElementById('sign-play');let lastRecords='';
const distanceTemplates={json_js({r:signage_panel(element_id='distance-sign-'+r) for r in ROOMS})};
function distancePanel(r){{return distanceTemplates[r];}}
function clock(s){{return new Date((14*3600+Math.floor(s))*1000).toISOString().slice(11,19);}}
function render(t,end){{
 document.getElementById('sign-clock').textContent=clock(t);document.getElementById('sign-position').textContent='CCTV '+clock(t)+' 기준';
 document.getElementById('sign-timeline').textContent=clock(t)+' / '+clock(end);seek.max=end||1;seek.value=t;
 const vals={{}},ids=[];
 for(const r of rooms){{const available=rows[r].filter(x=>x.t<=t+.001);let rec=available.length?available[available.length-1]:null;if(rec&&t>rows[r][rows[r].length-1].t+1.1)rec=null;vals[r]={{...(rec||{{}}),distance:distanceAt(rows[r],t)}};ids.push(r+':'+vals[r].distance.status+':'+vals[r].distance.stability+':'+vals[r].distance.reason);}}
 const id=ids.join('|');if(id===lastRecords)return;lastRecords=id;
 const best=recommendDistance(current,vals,cfg),rank=r=>distanceValue(vals[r]).reached_m??Infinity;
 const order=[current,...rooms.filter(r=>r!==current).sort((a,b)=>rank(a)-rank(b)||cfg.walk[current][a]-cfg.walk[current][b])];
 const panels=order.map(r=>{{const d=distanceValue(vals[r]),[state,color,cls]=distanceState(vals[r]),total=signageTotal(d,cfg.walk?.[current]?.[r]);
  document.getElementById('ring-'+r).setAttribute('stroke',color);document.getElementById('dot-'+r).setAttribute('fill',color);document.getElementById('tag-'+r).setAttribute('fill',color);document.getElementById('map-status-'+r).textContent=state;document.getElementById('map-wait-'+r).textContent=total;
  return `<div class="sg-item ${{cls}}">${{r===best?'<span class="badge">혼잡 단계 낮음</span>':''}}<h3>${{nums[r]}}번 · ${{roomNames[r]}} 화장실</h3><div id="sign-state-${{r}}">${{state}}</div><div class="minutes" id="sign-wait-${{r}}">${{total}}</div><footer>최종 예상 소요시간 · 임의 거리 기준 시연값</footer>${{distancePanel(r)}}</div>`;
 }}).join('');document.getElementById('sign-items').innerHTML=panels;
 rooms.forEach(r=>{{const d=distanceValue(vals[r]);paintDistance(document.getElementById('distance-sign-'+r),{{...d,wait:signageTotal(d,cfg.walk?.[current]?.[r])}});}});
 const route=document.getElementById('sign-route');route.style.display=best?'block':'none';
 if(best){{const [x,y]=pos[current],[xx,yy]=pos[best];route.setAttribute('d',`M${{x}} ${{y}} L400 ${{y}} L400 435 L${{xx}} 435 L${{xx}} ${{yy}}`);}}
 document.getElementById('sign-note').textContent='임의 거리 기준 시연값 · 최종 예상 소요시간은 도보 이동을 포함한 시연용 범위입니다. '+(best?'거리 혼잡 단계가 낮은 화장실 안내 · 정확한 실제 소요시간이나 가장 빠른 도착을 보장하지 않습니다.':'낮은 혼잡 단계가 없거나 측정 불가가 있으면 추천하지 않습니다.');
}}
const fallback=Math.max(0,...rooms.map(r=>rows[r].length?rows[r][rows[r].length-1].t:0));
const player=createPlayback({{videos,key:cfg.playback_key||'default',limit:cfg.playback_end,fallbackEnd:fallback,onTime:render,onState:playing=>{{button.disabled=playing;button.setAttribute('aria-pressed',String(playing));}},onError:message=>document.getElementById('sign-error').textContent=message}});
button.onclick=()=>player.play();document.getElementById('sign-pause').onclick=()=>player.pause();document.getElementById('sign-reset').onclick=()=>player.reset();seek.oninput=()=>player.seek(Number(seek.value));
</script>'''
