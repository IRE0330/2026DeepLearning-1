(function(){
 const button=document.getElementById('signage-fullscreen'),platform=window.signageScreenMode==='platform';
 let fit=document.querySelector('.wrap');
 if(!fit){fit=document.createElement('div');for(const child of [...document.body.children])if(child!==button&&child.tagName!=='SCRIPT'&&child.tagName!=='STYLE')fit.appendChild(child);document.body.insertBefore(fit,button);}
 fit.classList.add('screen-fit');
 let toolbar=document.querySelector('.bar');
 if(!toolbar){toolbar=document.createElement('div');toolbar.className='screen-toolbar';toolbar.style.cssText='display:flex;justify-content:flex-end;margin-bottom:10px';fit.prepend(toolbar);}
 toolbar.appendChild(button);
 function resize(){
  if(!document.body.classList.contains('screen-active'))return;
  const w=platform?1174:1500,h=platform?2180:Math.max(900,fit.scrollHeight);
  fit.style.width=w+'px';if(platform)fit.style.height=h+'px';
  const scale=Math.min(innerWidth/w,innerHeight/h);
  fit.style.transform='scale('+scale+')';fit.style.left=((innerWidth-w*scale)/2)+'px';fit.style.top=((innerHeight-h*scale)/2)+'px';
 }
 function activate(){document.body.appendChild(button);document.body.classList.add('screen-active');button.textContent='⛶ 전체화면 종료';resize();}
 function deactivate(){toolbar.appendChild(button);document.body.classList.remove('screen-active');fit.style.cssText='';button.textContent='⛶ 전체화면';}
 button.onclick=async()=>{
  if(document.fullscreenElement){await document.exitFullscreen();return;}
  if(document.body.classList.contains('screen-active')){deactivate();return;}
  try{await document.documentElement.requestFullscreen();activate();}
  catch(error){
   // Some embedded browsers disallow fullscreen; open a signage-only window.
   const popup=window.open('','_blank','popup=yes,width=1440,height=900');
   if(!popup){button.textContent='팝업 허용 후 다시 클릭';return;}
   popup.__signageResume=window.__signageClockState;
   popup.__signageStandalone=true;
   popup.document.open();popup.document.write('<!doctype html><html><head><meta charset="utf-8"><title>화장실 사이니지</title></head><body>'+document.body.innerHTML+'</body></html>');popup.document.close();
  }
 };
 document.addEventListener('fullscreenchange',()=>{if(document.fullscreenElement)activate();else if(!window.__signageStandalone)deactivate();});
 window.addEventListener('resize',resize);
 if(window.__signageStandalone)activate();
})();
