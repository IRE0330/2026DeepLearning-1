export default function(component) {
  const {data, parentElement, setTriggerValue} = component;
  const canvas=parentElement.querySelector('canvas'), ctx=canvas.getContext('2d');
  const status=parentElement.querySelector('[role=status]');
  const saved=data.setting||{}, lines=JSON.parse(JSON.stringify(saved.lines||{}));
  const meters=(data.meters||[5,10,15]).map(String);
  let origin=saved.origin||null, pending=null, mode='origin', image=null;
  const colors={'5':'#1976d2','10':'#c07800','15':'#c32948'};
  const controls=parentElement.querySelectorAll('[data-mode]');
  function message(){status.textContent=mode==='origin'?'대기줄이 시작하는 입구 쪽 점을 클릭하세요.':mode+'m 기준선의 '+(pending?'두 번째':'첫 번째')+' 끝점을 클릭하세요.';}
  function paint(){
    const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
    if(image)ctx.drawImage(image,0,0,w,h);
    else {ctx.fillStyle='#edf2f6';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#c7d4df';for(let x=0;x<w;x+=w/16){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}for(let y=0;y<h;y+=h/9){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}ctx.fillStyle='#34495e';ctx.font='20px sans-serif';ctx.fillText('설정 연습 · CCTV 영상 없음',20,35);}
    for(const m of meters)if(lines[m]){
      const [a,b]=lines[m];ctx.strokeStyle=colors[m];ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(a[0]*w,a[1]*h);ctx.lineTo(b[0]*w,b[1]*h);ctx.stroke();
      ctx.font='bold 18px sans-serif';ctx.fillStyle=colors[m];ctx.fillText(m+'m',(a[0]+b[0])*w/2+6,(a[1]+b[1])*h/2-8);
    }
    for(const p of [origin,pending].filter(Boolean)){ctx.fillStyle='#e34822';ctx.beginPath();ctx.arc(p[0]*w,p[1]*h,7,0,Math.PI*2);ctx.fill();}
    if(origin){ctx.fillStyle='#e34822';ctx.font='bold 16px sans-serif';ctx.fillText('시작점',origin[0]*w+10,origin[1]*h);}
    controls.forEach(b=>{b.hidden=['5','10','15'].includes(b.dataset.mode)&&!meters.includes(b.dataset.mode);b.disabled=!!data.disabled;b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});
    parentElement.querySelector('[data-save]').disabled=!!data.disabled;
    parentElement.querySelector('[data-clear]').disabled=!!data.disabled;
  }
  function choose(next){mode=next;pending=null;message();paint();}
  controls.forEach(b=>b.onclick=()=>choose(b.dataset.mode));
  canvas.onpointerdown=e=>{
    if(data.disabled)return;
    const box=canvas.getBoundingClientRect(), p=[Math.max(0,Math.min(1,(e.clientX-box.left)/box.width)),Math.max(0,Math.min(1,(e.clientY-box.top)/box.height))];
    if(mode==='origin'){origin=p;choose('5');}
    else if(!pending){pending=p;message();paint();}
    else {lines[mode]=[pending,p];const next=mode==='5'?'10':mode==='10'&&meters.includes('15')?'15':meters.at(-1);choose(next);if(meters.every(m=>lines[m]))status.textContent='지정을 마쳤습니다. 저장하거나 버튼을 선택해 다시 그리세요.';}
  };
  parentElement.querySelector('[data-clear]').onclick=()=>{origin=null;pending=null;for(const m of meters)delete lines[m];choose('origin');};
  parentElement.querySelector('[data-save]').onclick=()=>{
    if(!origin||meters.some(m=>!lines[m])){status.textContent='시작점과 활성 기준선 '+meters.length+'개를 모두 지정하세요.';return;}
    setTriggerValue('apply',{origin,lines,source_key:data.source_key});
  };
  canvas.width=data.width||960;canvas.height=data.height||540;
  if(data.image){image=new Image();image.onload=paint;image.src=data.image;}
  message();paint();
  return ()=>{canvas.onpointerdown=null;if(image)image.onload=null;};
}
