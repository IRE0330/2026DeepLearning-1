// Synthetic DOM stubs exercise event handling and playback wiring, not browser rendering.
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const vm=require('node:vm');

function element(){
  const children=new Map();
  return {textContent:'',style:{},dataset:{},innerHTML:'',disabled:false,
    setAttribute(k,v){this[k]=v;},getAttribute(k){return this[k];},
    querySelector(s){if(!children.has(s))children.set(s,element());return children.get(s);},
    replaceChildren(){},appendChild(){},addEventListener(){}};
}

async function editorTests(){
  const js=fs.readFileSync('busan_restroom_dashboard/distance_editor.js','utf8');
  const {default:mount}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
  function instance(data={}){
    const canvas=element(),status=element(),save=element(),clear=element();
    const context=new Proxy({},{get:()=>()=>{}});
    canvas.getContext=()=>context;canvas.getBoundingClientRect=()=>({left:100,top:50,width:480,height:270});
    const buttons=['origin','5','10','15'].map(mode=>({...element(),dataset:{mode}}));
    const parentElement={querySelector:s=>s==='canvas'?canvas:s==='[role=status]'?status:s==='[data-save]'?save:clear,querySelectorAll:()=>buttons};
    let emitted;
    const cleanup=mount({data,parentElement,setTriggerValue:(k,v)=>{emitted={k,v};}});
    return {canvas,status,save,clear,buttons,cleanup,get emitted(){return emitted;},click(x,y){canvas.onpointerdown({clientX:100+x*480,clientY:50+y*270});}};
  }
  const a=instance({source_key:'north'});
  a.save.onclick();assert.match(a.status.textContent,/모두 지정/);
  a.click(.5,.1);
  for(const y of [.3,.5,.7]){a.click(.1,y);a.click(.9,y);}
  a.save.onclick();assert.equal(a.emitted.k,'apply');assert.equal(a.emitted.v.source_key,'north');
  assert.deepEqual(a.emitted.v.origin,[.5,.1]);
  for(const [m,y] of [['5',.3],['10',.5],['15',.7]])assert.deepEqual(a.emitted.v.lines[m],[[.1,y],[.9,y]]);
  const b=instance({source_key:'south'});b.save.onclick();assert.equal(b.emitted,undefined);
  const c=instance({source_key:'north',setting:a.emitted.v});c.save.onclick();assert.deepEqual(c.emitted.v,a.emitted.v);
  c.clear.onclick();c.save.onclick();assert.match(c.status.textContent,/모두 지정/);
  const locked=instance({disabled:true});locked.click(.5,.1);assert.equal(locked.save.disabled,true);
  a.cleanup();assert.equal(a.canvas.onpointerdown,null);
  console.log('PASS editor: scaled mouse coordinates, 3 lines, validation, per-camera isolation, restore, clear, disabled, cleanup');
}

function playbackTests(folder){
  for(const [name,panelId,seekId] of [['dashboard','distance-north','seek'],['detail','distance-detail',null],['detail-east','distance-detail',null],['detail-south','distance-detail',null],['signage','distance-sign-north','sign-seek']]){
    const html=fs.readFileSync(path.join(folder,name+'.html'),'utf8');
    assert.match(html,/임의 거리 기준 시연값/);
    assert.doesNotMatch(html,/"expected_wait_s"\s*:/);
    assert.doesNotMatch(html,/"wait"\s*:\s*28/);
    const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
    const nodes=new Map();
    const get=id=>{if(/^(v-|sign-video-)/.test(id)||id==='detail-video')return null;if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
    const context=vm.createContext({document:{getElementById:get,createElement:()=>element()},
      localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){}},
      requestAnimationFrame(){},performance:{now:()=>100},console,URL});
    for(const source of scripts)new vm.Script(source).runInContext(context);
    assert.equal(get(panelId).querySelector('[data-distance="status"]').textContent,'측정 불가');
    for(const [t,expected,wait] of [[1,'여유','1분 미만'],[4,'보통','1분 이상'],[6,'혼잡','2분 이상'],[8,'매우 혼잡','3분 이상']]){
      if(seekId){get(seekId).value=t;get(seekId).oninput();}
      else vm.runInContext('update('+t+')',context);
      assert.equal(get(panelId).querySelector('[data-distance="status"]').textContent,expected,name+' at '+t);
      assert.equal(get(panelId).querySelector('[data-distance="wait"]').textContent,wait);
      if(name==='dashboard')for(const room of ['north','east','south']){
        assert.equal(get(room+'-status').textContent,expected);
        assert.equal(get(room+'-wait').textContent,wait);
        assert.equal(get(room+'-queue').textContent,'1 명');
      }
      if(name.startsWith('detail')){
        assert.equal(get('detail-status').textContent,expected);
        assert.equal(get('detail-wait').textContent,wait);
        assert.equal(get('detail-congestion-wait').textContent,wait);
        assert.equal(get('detail-queue').textContent,'1명');
      }
      if(name==='signage')for(const room of ['north','east','south']){
        assert.equal(get('map-status-'+room).textContent,expected);
        assert.equal(get('map-wait-'+room).textContent,wait);
        assert.ok(get('sign-items').innerHTML.includes(wait));
      }
    }
    // Outside coverage clears the distance result instead of retaining the last band.
    // A legacy-only 28-second record, and times outside coverage, stay unavailable.
    for(const t of [12,14]){
    if(name==='dashboard')vm.runInContext('t='+t+';render()',context);
    else if(name.startsWith('detail'))vm.runInContext('update('+t+')',context);
    else vm.runInContext('render('+t+','+t+')',context);
    assert.equal(get(panelId).querySelector('[data-distance="status"]').textContent,'측정 불가');
    assert.equal(get(panelId).querySelector('[data-distance="wait"]').textContent,'측정 불가');
    if(name==='dashboard')assert.equal(get('north-wait').textContent,'측정 불가');
    if(name.startsWith('detail'))assert.equal(get('detail-congestion-wait').textContent,'측정 불가');
    if(name==='signage')assert.equal(get('map-wait-north').textContent,'측정 불가');
    }
    // Backward seek uses the target timestamp, never the last rendered band.
    if(seekId){get(seekId).value=4;get(seekId).oninput();}
    else vm.runInContext('update(4)',context);
    assert.equal(get(panelId).querySelector('[data-distance="wait"]').textContent,'1분 이상');
    // A paused frame does not expire when wall-clock time advances.
    if(seekId){get(seekId).value=9;get(seekId).oninput();}
    else vm.runInContext('update(9)',context);
    assert.equal(get(panelId).querySelector('[data-distance="stability"]').textContent,'최근 판정 유지');
    context.performance.now=()=>1e9;
    if(name==='dashboard')get('pause').onclick();
    else if(name==='signage')get('sign-pause').onclick();
    else vm.runInContext('update(9)',context);
    assert.equal(get(panelId).querySelector('[data-distance="wait"]').textContent,'3분 이상');
    // Expiry between records must not wait for the next saved row.
    if(name==='dashboard')vm.runInContext('t=11.001;render()',context);
    else if(name.startsWith('detail'))vm.runInContext('update(11.001)',context);
    else vm.runInContext('render(11.001,12)',context);
    assert.equal(get(panelId).querySelector('[data-distance="wait"]').textContent,'측정 불가');
    if(name==='dashboard')get('reset').onclick();
    else if(name==='signage')get('sign-reset').onclick();
    else vm.runInContext('update(0)',context);
    assert.equal(get(panelId).querySelector('[data-distance="status"]').textContent,'측정 불가');
    console.log('PASS playback:',name,'all 4 bands, waiting labels, missing/out-of-range data');
  }
  const staticHtml=fs.readFileSync(path.join(folder,'static.html'),'utf8');
  assert.match(staticHtml,/거리 기준 혼잡도 · <span data-distance="status">매우 혼잡/);
  assert.match(staticHtml,/임의 거리 기준 시연값/);
  const unavailable=fs.readFileSync(path.join(folder,'static-unknown.html'),'utf8');
  assert.match(unavailable,/id="sign-wait-north">측정 불가/);
  assert.doesNotMatch(unavailable,/28초/);
  console.log('PASS static signage export');
}

editorTests().then(()=>playbackTests(process.argv[2]||'.local-run/distance-ui-test')).catch(e=>{console.error(e);process.exitCode=1;});
