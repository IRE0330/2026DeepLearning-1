// Run the actual controller with deterministic media events, promises and clocks.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('busan_restroom_dashboard/playback.js','utf8');
const storage=new Map();let now=1_000_000;
const flush=async()=>{for(let i=0;i<6;i++)await Promise.resolve();};
function mount({key='run-a',count=3,mode='ok',ready=4,limit=90}={}){
  const windowEvents={},frames=[],states=[],errors=[],buttons=[];let resolve;
  const pending=new Promise(r=>resolve=r);
  const videos=Array.from({length:count},()=>{
    const events={};return {duration:100,currentTime:0,readyState:ready,paused:true,ended:false,seeking:false,
      parentElement:{appendChild:b=>buttons.push(b)},setAttribute(){},addEventListener:(k,f)=>events[k]=f,
      emit(k){events[k]?.();},pause(){this.paused=true;this.emit('pause');},
      play(){if(mode==='blocked')return Promise.reject({name:'NotAllowedError'});
        if(mode==='pending')return pending.then(()=>{this.paused=false;});
        if(mode!=='false-success')this.paused=false;this.emit('play');return Promise.resolve();}
    };
  });
  const context=vm.createContext({Date:{now:()=>now},performance:{now:()=>now},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
    window:{addEventListener:(k,f)=>windowEvents[k]=f},requestAnimationFrame:f=>frames.push(f),
    document:{baseURI:'http://localhost:8501/',createElement:()=>({style:{},setAttribute(){},remove(){this.removed=true;}})},URL});
  vm.runInContext(source,context);context.opts={videos,key,limit,fallbackEnd:limit,onState:p=>states.push(p),onError:e=>errors.push(e)};
  const player=vm.runInContext('createPlayback(opts)',context);
  return {player,videos,states,errors,buttons,resolve,hide:()=>windowEvents.pagehide(),tick(){frames.shift()?.();},
    stored:()=>JSON.parse(storage.get('busan-cctv-playback-v5:'+key)||'null')};
}
async function test(name,fn){storage.clear();now=1_000_000;await fn();console.log('PASS',name);}
(async()=>{
  await test('elapsed-time restore across dashboard/detail/signage; actual play confirmed',async()=>{
    const a=mount();a.player.seek(12);a.player.play();assert.equal(a.player.getState().playing,false);
    await flush();assert.equal(a.player.getState().playing,true);
    a.videos.forEach(v=>v.currentTime=13);a.hide();assert.equal(a.stored().t,13);assert.equal(a.stored().playing,true);
    assert.ok(a.videos.every(v=>v.paused));now+=5000;
    const b=mount({count:1});assert.equal(b.player.getState().t,18);assert.equal(b.player.getState().playing,false);
    await flush();assert.equal(b.player.getState().playing,true);b.hide();now+=2000;
    const c=mount();await flush();assert.equal(c.player.getState().t,20);assert.equal(c.player.getState().playing,true);
  });
  await test('explicit pause remains paused across navigation',async()=>{
    const a=mount();a.player.seek(17);a.player.play();await flush();a.player.pause();a.hide();now+=9000;
    const b=mount();await flush();assert.equal(b.player.getState().t,17);assert.equal(b.player.getState().playing,false);
    assert.ok(b.videos.every(v=>v.paused));
  });
  await test('autoplay rejection freezes restored position and offers a working resume button',async()=>{
    const a=mount();a.player.seek(10);a.player.play();await flush();a.hide();now+=4000;
    const b=mount({count:1,mode:'blocked'});await flush();assert.equal(b.player.getState().t,14);
    assert.equal(b.player.getState().playing,false);assert.equal(b.stored().playing,false);assert.equal(b.states.some(Boolean),false);
    assert.match(b.errors[0],/차단/);assert.equal(b.buttons.length,1);now+=5000;b.tick();assert.equal(b.player.getState().t,14);
    b.videos[0].play=function(){this.paused=false;return Promise.resolve();};b.buttons[0].onclick();await flush();
    assert.equal(b.player.getState().playing,true);assert.equal(b.player.getState().t,14);
  });
  await test('pending/unsuccessful media never reports playing; late success cannot undo pause',async()=>{
    const a=mount({mode:'pending'});a.player.play();assert.equal(a.states.some(Boolean),false);a.player.pause();a.resolve();await flush();
    assert.equal(a.player.getState().playing,false);assert.ok(a.videos.every(v=>v.paused));
    const b=mount({key:'false-success',mode:'false-success'});b.player.play();await flush();assert.equal(b.states.some(Boolean),false);
    assert.equal(b.errors.length,1);
  });
  await test('metadata delay counts elapsed time; pause cancels deferred autoplay',async()=>{
    const a=mount();a.player.seek(5);a.player.play();await flush();a.hide();now+=2000;
    const b=mount({ready:0});assert.equal(b.player.getState().t,7);now+=3000;
    for(const v of b.videos){v.readyState=4;v.emit('loadedmetadata');}await flush();assert.equal(b.player.getState().t,10);
    assert.equal(b.player.getState().playing,true);b.hide();
    const c=mount({ready:0});c.player.pause();now+=3000;
    for(const v of c.videos){v.readyState=4;v.emit('loadedmetadata');}await flush();assert.equal(c.player.getState().playing,false);
  });
  await test('end clamps without automatic rewind; explicit play can restart',async()=>{
    const a=mount();a.player.seek(88);a.player.play();await flush();a.hide();now+=5000;
    const b=mount();await flush();assert.equal(b.player.getState().t,90);assert.equal(b.player.getState().playing,false);
    b.player.play();await flush();assert.equal(b.player.getState().t,0);assert.equal(b.player.getState().playing,true);
  });
  await test('new analysis/video key is isolated; old/malformed state is safely paused',async()=>{
    const a=mount();a.player.seek(20);a.player.play();await flush();a.hide();
    const b=mount({key:'run-b'});await flush();assert.equal(b.player.getState().t,0);assert.equal(b.player.getState().playing,false);
    storage.set('busan-cctv-playback-v5:legacy',JSON.stringify({t:11,end:90}));
    const c=mount({key:'legacy'});await flush();assert.equal(c.player.getState().t,11);assert.equal(c.player.getState().playing,false);
    storage.set('busan-cctv-playback-v5:bad','{invalid');assert.equal(mount({key:'bad'}).player.getState().t,0);
  });
  await test('seek/reset and native control commands preserve group behavior',async()=>{
    const a=mount();a.videos[1].currentTime=9;a.videos[1].emit('pointerdown');a.videos[1].paused=false;a.videos[1].emit('play');await flush();
    assert.equal(a.player.getState().playing,true);a.player.seek(25);assert.ok(a.videos.every(v=>v.currentTime===25));
    a.videos[1].emit('pointerdown');a.videos[1].pause();assert.equal(a.player.getState().playing,false);
    a.player.reset();assert.equal(a.stored().t,0);assert.equal(a.stored().playing,false);
  });
})().catch(e=>{console.error(e);process.exitCode=1;});
