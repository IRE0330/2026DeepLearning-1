const pc=platformConfig;
if(window.__signageResume){pc.day=window.__signageResume.day;pc.start=window.__signageResume.start;}
const bands={'대기 없음':[0,0],'5m 미만':[0,5],'5m 이상 ~ 10m 미만':[5,10],'10m 이상 ~ 15m 미만':[10,15],'15m 이상':[15,null]};
const waitRanks={'대기 없음':0,'5m 미만':1,'5m 이상 ~ 10m 미만':2,'10m 이상 ~ 15m 미만':3,'15m 이상':4};
function congestionState(band){return !band?'unknown':band[1]===0?'no-wait':band[0]>=15?'very-crowded':band[0]>=10?'crowded':band[0]>=5?'normal':'free';}
function waitingLabel(row){return row?.distance==='대기 없음'?'대기 없음':row?.wait||'예측 정보 없음';}
function recommendationOrder(a,b){return (a.score??Infinity)-(b.score??Infinity)||a.walk-b.walk||a.number-b.number;}
function chooseBest(candidates){return candidates.every(r=>r.band)?[...candidates].sort(recommendationOrder)[0]:null;}
function minuteKey(d){return d.toISOString().slice(0,16).replace('T',' ');}
function totalLabel(b,w){if(b[0]===b[1])return (w+b[0])+'분';if(b[1]===null)return (w+b[0])+'분 이상';return (w+b[0])+'분 이상 '+(w+b[1])+'분 미만';}
function evaluateRoutes(now){
 return pc.routes.map(r=>{const arrival=new Date(now.getTime()+r.walk*60000),row=(pc.forecasts[minuteKey(arrival)]||{})[r.id],band=bands[row?.distance];
 return {...r,arrival,row,band,score:band?waitRanks[row.distance]:null,total:band?totalLabel(band,r.walk):'예측 정보 없음'};});
}
const el=id=>document.getElementById(id),text=(id,v)=>el(id).textContent=v;
let lastMinute='';
function drawPlatform(now){
 window.__signageClockState={...(window.__signageClockState||{}),day:now.toISOString().slice(0,10),start:now.toISOString().slice(11,19)};
 text('now',now.toISOString().slice(11,19));text('updated','업데이트 '+now.toISOString().slice(11,19));text('day',now.toISOString().slice(0,10));
 const key=minuteKey(now);if(key===lastMinute)return;lastMinute=key;
 const candidates=evaluateRoutes(now),complete=candidates.every(r=>r.band);
 const best=chooseBest(candidates);
 el('route').hidden=!best;el('no-data').hidden=!!best;el('hero').classList.toggle('missing',!best);
 if(best){
  document.querySelector('.summary').className='summary '+congestionState(best.band);
  text('direction',best.direction.replace(' 후 ',' 후\n'));text('walk','도보 '+best.walk+'분');text('route-walk','도보 '+best.walk+'분');
  el('route-image').src=best.image;el('route-image').alt=best.number+'번 화장실 경로 안내도';
  text('destination-number',best.number);text('destination',best.number+'번 화장실');text('arrival','도착 예정 '+best.arrival.toISOString().slice(11,19));
  text('total',waitingLabel(best.row));text('wait','도착 시각 기준 · 도보시간 별도');
 }else{
  text('direction','추천 정보 없음');text('walk','도착 시 예측을 확인해 주세요');
  text('no-data','전체 화장실의 도착 시 예측이 있어야 최단 추천을 비교할 수 있습니다. 날짜·CSV 범위를 확인하세요.');
 }
 el('alternatives').replaceChildren();
 for(const r of candidates.filter(r=>!best||r.number!==best.number).sort(recommendationOrder)){
  const card=document.createElement('div');
  const state=congestionState(r.band);
  card.className='item '+state;
  const head=document.createElement('div');head.className='item-head';
  const num=document.createElement('span');num.className='item-number';num.textContent=String(r.number).padStart(2,'0');
  const labels=document.createElement('div'),name=document.createElement('b'),direction=document.createElement('small');
  name.textContent=r.number+'번 화장실';direction.textContent=r.direction;labels.append(name,direction);
  const badge=document.createElement('span');badge.className='badge';badge.textContent=state==='unknown'?'정보 없음':state==='no-wait'?'대기 없음':state==='very-crowded'?'매우 혼잡':state==='crowded'?'혼잡':state==='normal'?'보통':'여유';
  head.append(num,labels,badge);
  const bottom=document.createElement('div');bottom.className='item-bottom';
  const caption=document.createElement('small');caption.textContent='예상 대기시간';
  const value=document.createElement('strong');value.textContent=waitingLabel(r.row);
  bottom.append(caption,value);
  const arrival=document.createElement('small');arrival.className='item-arrival';arrival.textContent='도보 '+r.walk+'분 · 도착 '+r.arrival.toISOString().slice(11,16);
  card.append(head,bottom,arrival);el('alternatives').appendChild(card);
 }
}
// Shared simulation clock starts with confirmed CCTV playback and continues after video ends.
const sharedClockKey='busan-platform-clock:'+pc.key;
const sharedBase=Date.parse(pc.day+'T14:00:00Z');
function readShared(){
 try{return JSON.parse(localStorage.getItem(sharedClockKey)||'null')||{};}catch{return {};}
}
function sharedSeconds(state=readShared()){
 const t=Number.isFinite(state.t)?Math.max(0,state.t):0;
 const elapsed=state.running&&Number.isFinite(state.savedAt)?Math.max(0,(Date.now()-state.savedAt)/1000):0;
 return t+elapsed*(Number(state.speed)||1);
}
function writeShared(t,running,speed){
 try{localStorage.setItem(sharedClockKey,JSON.stringify({t:Math.max(0,t),running,speed,savedAt:Date.now()}));}catch{}
}
function runSharedPlatform(){
 el('play-controls').innerHTML='<div class="bar"><button id="platform-play">재생</button><button id="platform-pause">일시정지</button><button id="platform-reset">처음부터</button><select id="platform-speed" aria-label="재생 배속"><option value="1">1배속</option><option value="10">10배속</option><option value="30">30배속</option><option value="60">60배속</option></select><input id="platform-seek" type="range" min="0" max="86399" step="1" aria-label="시연 시간 이동"></div><div class="note" id="platform-clock-state"></div>';
 const seek=el('platform-seek'),speedEl=el('platform-speed');
 function tick(){
  const state=readShared(),seconds=sharedSeconds(state),speed=Number(state.speed)||1;
  drawPlatform(new Date(sharedBase+seconds*1000));
  if(document.activeElement!==seek)seek.value=Math.min(86399,Math.floor(seconds));
  speedEl.value=String([1,10,30,60].includes(speed)?speed:1);
  el('platform-play').disabled=!!state.running;
  el('platform-pause').disabled=!state.running;
  text('platform-clock-state',state.running?'시연 시각 재생 중 · '+speed+'배속':'시연 시각 일시정지 · CCTV 재생 버튼과 연동');
  setTimeout(tick,250);
 }
 el('platform-play').onclick=()=>{const s=readShared();writeShared(sharedSeconds(s),true,Number(s.speed)||1);};
 el('platform-pause').onclick=()=>{const s=readShared();writeShared(sharedSeconds(s),false,Number(s.speed)||1);};
 el('platform-reset').onclick=()=>{writeShared(0,false,Number(readShared().speed)||1);};
 seek.oninput=e=>{const s=readShared();writeShared(Number(e.target.value),!!s.running,Number(s.speed)||1);};
 speedEl.onchange=e=>{const s=readShared();writeShared(sharedSeconds(s),!!s.running,Number(e.target.value));};
 tick();
}
// Independent CSV clock: never clamped to a CCTV duration.
function createCsvClock(start,end,initial){
 let current=Math.max(start,Math.min(end,initial)),running=false,speed=1,last=null;
 return {
  advance(now){if(last!==null&&running){current=Math.min(end,current+Math.max(0,now-last)*speed);if(current>=end)running=false;}last=now;return current;},
  play(now){last=now;running=current<end;},pause(now){this.advance(now);running=false;},
  seek(value,now){current=Math.max(start,Math.min(end,value));last=now;if(current>=end)running=false;},
  rate(value,now){this.advance(now);speed=value;},
  state(){return {current,running,speed};}
 };
}
if(pc.syncWithCctv){runSharedPlatform();}
else if(pc.follow){
 const keys=Object.keys(pc.forecasts).filter(k=>k.startsWith(pc.day+' ')).sort();
 if(!keys.length){drawPlatform(new Date(pc.day+'T'+pc.start+'Z'));el('play-controls').textContent='선택한 날짜의 CSV 기록이 없습니다.';}
 else{
  const parse=k=>Date.parse(k.replace(' ','T')+':00Z');
  const first=parse(keys[0]),end=parse(keys[keys.length-1]);
  const initial=Date.parse(pc.day+'T'+pc.start+'Z');
  const clock=createCsvClock(first,end,initial);
  el('play-controls').innerHTML='<div class="bar"><button id="platform-play">재생</button><button id="platform-pause">일시정지</button><button id="platform-reset">처음부터</button><select id="platform-speed" aria-label="재생 배속"><option value="1">1배속</option><option value="10">10배속</option><option value="30">30배속</option><option value="60">60배속</option></select><input id="platform-seek" type="range" step="1000" aria-label="CSV 재생 시각"></div><div class="note" id="platform-clock-state"></div>';
  const seek=el('platform-seek');seek.min=first;seek.max=end;
  function paint(){const state=clock.state();window.__signageClockState={...(window.__signageClockState||{}),running:state.running,speed:state.speed};drawPlatform(new Date(state.current));seek.value=state.current;el('platform-play').disabled=state.running;el('platform-pause').disabled=!state.running;text('platform-clock-state',state.current>=end?'CSV 마지막 시각에 도달했습니다.':state.running?'CSV 시각 재생 중 · '+state.speed+'배속':'CSV 시각 일시정지');}
  el('platform-play').onclick=()=>{clock.play(performance.now());paint();};
  el('platform-pause').onclick=()=>{clock.pause(performance.now());paint();};
  el('platform-reset').onclick=()=>{clock.pause(performance.now());clock.seek(first,performance.now());paint();};
  seek.oninput=e=>{clock.seek(Number(e.target.value),performance.now());paint();};
  el('platform-speed').onchange=e=>{clock.rate(Number(e.target.value),performance.now());paint();};
  function tick(now){clock.advance(now);paint();requestAnimationFrame(tick);}
  if(window.__signageResume){clock.rate(window.__signageResume.speed||1,performance.now());el('platform-speed').value=window.__signageResume.speed||1;if(window.__signageResume.running)clock.play(performance.now());}
  paint();requestAnimationFrame(tick);
 }
}else drawPlatform(new Date(pc.day+'T'+pc.start+'Z'));
