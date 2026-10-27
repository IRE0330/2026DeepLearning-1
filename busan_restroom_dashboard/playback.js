/* Keep iframe-local media; persist a timestamped timeline across menu reruns. */
function createPlayback(opts) {
  const videos=(opts.videos||[]).filter(Boolean);
  const key='busan-cctv-playback-v5:'+opts.key,gestures=new WeakMap();
  let t=0,end=Number(opts.fallbackEnd)||0,wanted=false,epoch=0,lead=videos[0];
  let gone=false,lastPaint=-1,lastWrite=0,interacted=false,confirmed=false;
  let restore=null,resumeButton=null;
  const onTime=opts.onTime||(()=>{}),onState=opts.onState||(()=>{});
  function isPlaying(){return confirmed&&wanted&&videos.length>0&&videos.every(v=>!v.paused&&!v.ended&&v.readyState>=2);}
  function paint(force=false){const tick=Math.floor(t*10);if(force||tick!==lastPaint){lastPaint=tick;onTime(t,end);}onState(isPlaying());}
  function save(force=false){if(gone)return;const now=performance.now();if(!force&&now-lastWrite<250)return;lastWrite=now;try{localStorage.setItem(key,JSON.stringify({version:2,t,end,playing:isPlaying(),savedAt:Date.now()}));}catch{}}
  function sample(){if(confirmed&&wanted&&lead&&lead.readyState>=2&&!lead.seeking&&Number.isFinite(lead.currentTime))t=Math.max(0,Math.min(end||lead.currentTime,lead.currentTime));}
  function clearResume(){if(resumeButton){resumeButton.remove?.();resumeButton=null;}}
  function duration(){const ds=videos.map(v=>v.duration).filter(d=>Number.isFinite(d)&&d>0);if(ds.length)end=Math.min(...ds);if(Number(opts.limit)>0)end=end>0?Math.min(end,Number(opts.limit)):Number(opts.limit);if(end>0)t=Math.min(t,end);}
  function align(v,force=false){if(v.readyState<1||!Number.isFinite(v.duration))return;const at=Math.min(t,v.duration);if(force||Math.abs(v.currentTime-at)>.3){try{v.currentTime=at;}catch{}}}
  function stopMedia(){videos.forEach(v=>v.pause());}
  function pause(){videos.forEach(v=>gestures.set(v,0));interacted=true;restore=null;sample();epoch++;wanted=false;confirmed=false;stopMedia();videos.forEach(v=>align(v));clearResume();paint(true);save(true);}
  function errorMessage(error){return error?.name==='NotAllowedError'?'브라우저가 자동 재생을 차단했습니다. 현재 위치에서 재개 버튼 또는 재생 버튼을 눌러주세요.':error?.name==='NotSupportedError'?'영상 형식을 재생할 수 없습니다. 시연 설정에서 재생용 MP4를 만든 뒤 다시 연결해주세요.':'영상 재생에 실패했습니다. 영상 연결과 재생용 MP4를 확인하고 다시 재생해주세요.';}
  function report(v,error){const text=errorMessage(error);if(opts.onError)opts.onError(text);if(opts.onVideoError&&v)opts.onVideoError(v,text);
    // The detail view only has native controls. Offer a gesture inside its iframe.
    if(!resumeButton&&typeof document!=='undefined'&&document.createElement&&v?.parentElement){
      resumeButton=document.createElement('button');resumeButton.type='button';resumeButton.textContent='▶ 재개';resumeButton.setAttribute('aria-label','현재 위치에서 CCTV 재개');
      resumeButton.style.cssText='position:absolute;right:12px;top:48px;z-index:10';resumeButton.onclick=()=>start();v.parentElement.appendChild(resumeButton);
    }
  }
  function start(automatic=false){
    if(gone)return;
    videos.forEach(v=>gestures.set(v,0));if(!automatic)interacted=true;restore=null;duration();
    if(end>0&&t>=end){if(automatic){wanted=false;confirmed=false;paint(true);save(true);return;}t=0;}
    if(!videos.length||(opts.expectedVideos&&videos.length!==opts.expectedVideos)){wanted=false;paint(true);if(opts.onError)opts.onError(opts.expectedVideos?'세 CCTV 영상이 모두 연결되어야 동시 재생할 수 있습니다. 영상 연결을 확인해주세요.':'재생할 영상이 없습니다. 영상 연결을 확인해주세요.');return;}
    const token=++epoch;wanted=true;confirmed=false;clearResume();
    // Do not await metadata or a different video before issuing the other play calls.
    const attempts=videos.map(v=>{
      v.muted=true;v.defaultMuted=true;v.playsInline=true;
      v.setAttribute?.('muted','');v.setAttribute?.('playsinline','');
      align(v);
      try{return Promise.resolve(v.play());}catch(error){return Promise.reject(error);}
    });
    paint(true);
    Promise.allSettled(attempts).then(results=>{
      if(gone||token!==epoch){if(!wanted)stopMedia();return;}
      const rejected=results.findIndex(result=>result.status==='rejected');
      if(rejected>=0){wanted=false;confirmed=false;epoch++;stopMedia();videos.forEach(v=>align(v,true));paint(true);save(true);report(videos[rejected],results[rejected].reason);return;}
      if(!wanted){stopMedia();return;}
      if(videos.some(v=>v.paused||v.ended)){wanted=false;stopMedia();paint(true);save(true);report(videos[0],{name:'AbortError'});return;}
      confirmed=true;
      lead=videos.find(v=>!v.paused&&!v.ended)||videos[0];paint(true);save(true);
    });
    save(true);
  }
  try{const state=JSON.parse(localStorage.getItem(key)||'null');if(Number.isFinite(state?.t)){
    t=Math.max(0,state.t);
    if(state.playing===true&&Number.isFinite(state.savedAt)&&state.savedAt>0)restore=state;
  }}catch{}
  function restoreTime(){if(restore)t=Math.max(0,restore.t)+Math.max(0,(Date.now()-restore.savedAt)/1000);duration();}
  function tryRestore(){
    if(!restore||gone||interacted)return;
    restoreTime();videos.forEach(v=>align(v));
    if(videos.length&&videos.every(v=>v.readyState>=1&&Number.isFinite(v.duration)))start(true);
  }
  videos.forEach(v=>{
    v.muted=true;v.defaultMuted=true;v.playsInline=true;v.preload='auto';
    // Relative /media URLs must resolve against the app, including in srcdoc frames.
    try{if(v.getAttribute&&v.getAttribute('src'))v.src=new URL(v.getAttribute('src'),document.baseURI).href;}catch{}
    v.addEventListener('loadedmetadata',()=>{duration();align(v);tryRestore();paint(true);});
    v.addEventListener('seeked',()=>{if(v===lead&&!wanted&&interacted){t=Math.min(end||v.currentTime,v.currentTime);videos.filter(x=>x!==v).forEach(x=>align(x));paint(true);save(true);}});
    v.addEventListener('ended',()=>{if(wanted&&v===lead&&v.ended){t=end||v.currentTime;wanted=false;confirmed=false;epoch++;stopMedia();paint(true);save(true);}});
    v.addEventListener('error',()=>{if(!wanted&&!restore)return;restore=null;sample();wanted=false;confirmed=false;epoch++;stopMedia();paint(true);save(true);report(v,v.error);});
    // Only an actual interaction with native video controls may command the group.
    const gesture=()=>{gestures.set(v,performance.now()+1500);};
    v.addEventListener('pointerdown',gesture);v.addEventListener('touchstart',gesture);v.addEventListener('keydown',gesture);
    v.addEventListener('play',()=>{if(performance.now()<(gestures.get(v)||0)&&!wanted){gestures.set(v,0);lead=v;t=v.currentTime;start();}else if(!wanted){v.pause();}});
    v.addEventListener('pause',()=>{if(performance.now()<(gestures.get(v)||0)&&wanted&&v.paused){gestures.set(v,0);lead=v;pause();}});
  });
  // Storage restores positions across pages; another frame cannot cancel local buttons.
  window.addEventListener('storage',event=>{if(interacted||wanted||restore||event.key!==key||!event.newValue)return;try{const state=JSON.parse(event.newValue);if(Number.isFinite(state.t)){t=Math.max(0,Math.min(end||state.t,state.t));videos.forEach(v=>align(v));paint(true);}}catch{}});
  window.addEventListener('pagehide',()=>{sample();save(true);gone=true;restore=null;wanted=false;confirmed=false;epoch++;stopMedia();});
  function frame(){
    if(gone)return;
    // A delayed play event/promise or a browser seek must not undo explicit pause.
    if(!wanted)for(const v of videos)if(!v.paused)v.pause();
    if(confirmed&&wanted&&lead&&lead.readyState>=2&&!lead.paused&&!lead.seeking){
      t=Math.min(end||lead.currentTime,lead.currentTime);
      if(end>0&&t>=end){wanted=false;epoch++;stopMedia();paint(true);save(true);}
      else for(const v of videos)if(v!==lead&&v.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-t)>.35)align(v);
      save();
    }
    paint();requestAnimationFrame(frame);
  }
  restoreTime();videos.forEach(v=>align(v));paint(true);tryRestore();requestAnimationFrame(frame);
  return {
    play(){start();},pause,
    toggle(){if(wanted)pause();else start();},
    seek(value){value=Number(value);if(!Number.isFinite(value))return;interacted=true;restore=null;t=Math.max(0,Math.min(end||value,value));videos.forEach(v=>align(v,true));paint(true);save(true);},
    reset(){interacted=true;restore=null;epoch++;wanted=false;confirmed=false;stopMedia();clearResume();t=0;videos.forEach(v=>align(v,true));paint(true);save(true);},
    getState(){return {t,playing:isPlaying(),end};}
  };
}
