"""Shared distance-only presentation for existing playback views."""
import html
from distance_demo import DISCLAIMER, unavailable, settings_for
from distance_policy import active_meters


def panel(result=None, element_id='distance-result'):
    from distance_stability import waiting
    from cctv_presentation import status_text
    result = result or waiting()
    esc = lambda x: html.escape(str(x), quote=True)
    reached = result.get('reached_m')
    reach = reach_label(result)
    note=DISCLAIMER+(' · 시연 추정' if result.get('overflow') else '')
    stability=result.get('stability','측정 불가' if reached is None else '유효 관측')
    result={**result,'status':status_text(result)}
    return f'''<section id="{esc(element_id)}" class="distance-demo" aria-live="polite" style="padding:12px;border-top:1px solid #d6e1eb;background:#f5f8fc;line-height:1.7"><strong>거리 기준 혼잡도 · <span data-distance="status">{esc(result['status'])}</span></strong><div>예상 대기시간: <b data-distance="wait">{esc(result['wait'])}</b></div><strong data-distance="stability">{esc(stability)}</strong><div data-distance="reach">{esc(reach)}</div><small data-distance="reason">{esc(result['reason'])}</small><div data-distance="assumption" style="font-size:11px;color:#566b80">{esc(note)}</div></section>'''


def overlay(cfg, room):
    # Draw saved annotations on the media actually displayed. This does not
    # rebind old observations to a replacement video for distance evaluation.
    display_cfg={**cfg,'videos':cfg.get('display_videos',cfg.get('videos',{})),
                 'distance_video_keys':{}}
    setting, key = settings_for(display_cfg, room)
    if not key or setting.get('source_key') != key:
        return ''
    from distance_demo import validate_lines
    if validate_lines(setting,active_meters(room)):
        return ''
    shapes = []
    for m, color in [('5','#59b2ff'),('10','#ffcc54'),('15','#ff627d')]:
        if int(m) not in active_meters(room):continue
        a,b=setting['lines'][m]
        text_x=max(8,min(940,(a[0]+b[0])*500))
        text_y=max(28,min(980,(a[1]+b[1])*500-8))
        shapes.append(f'<line x1="{a[0]*1000}" y1="{a[1]*1000}" x2="{b[0]*1000}" y2="{b[1]*1000}" stroke="{color}" stroke-width="4"/><text x="{text_x}" y="{text_y}" fill="{color}" font-size="24">{m}m</text>')
    origin=setting['origin']
    shapes.append(f'<circle data-distance-origin cx="{origin[0]*1000}" cy="{origin[1]*1000}" r="7" fill="#ff8c42"/><text x="{max(8,min(880,origin[0]*1000+12))}" y="{max(28,min(980,origin[1]*1000-10))}" fill="#ff8c42" font-size="23">시작점</text>')
    boundary=setting.get('overflow_boundary') if room in ('south','east') else None
    if boundary:
        from distance_policy import validate_boundary
        if not validate_boundary(boundary):
            a,b=boundary
            shapes.append(f'<line data-overflow-boundary x1="{a[0]*1000}" y1="{a[1]*1000}" x2="{b[0]*1000}" y2="{b[1]*1000}" stroke="#c786ff" stroke-dasharray="10 6" stroke-width="6"/>')
            shapes.append(f'<text data-overflow-boundary-label x="{max(8,min(875,(a[0]+b[0])*500))}" y="{max(28,min(980,(a[1]+b[1])*500-12))}" fill="#c786ff" font-size="23">연결 경계</text>')
    return f'''<svg id="distance-overlay-{room}" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="임의 거리 기준 시연선과 마지막 대기자 위치" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none">{''.join(shapes)}<circle data-tail r="9" fill="#fff" stroke="#e34822" stroke-width="4" visibility="hidden"/><text data-tail-label font-size="20" fill="#fff" stroke="#172431" stroke-width=".4" visibility="hidden"/></svg>'''


def script():
    return '''
function distanceValue(record) {
 return record?.distance||distanceWaiting();
}
function distanceWaiting(reason='정상 거리 관측을 기다리고 있습니다.') {
 return {status:'대기정보 확인 중',wait:'대기정보 확인 중',reached_m:null,tail:null,held:false,stability:'대기정보 확인 중',reason,retain_last:true,last_valid_time_s:null};
}
function distanceMedia(videos) {
 return {ended:videos.some(v=>v?.ended&&!v.error),failed:videos.some(v=>v?.error),delayed:videos.some(v=>v&&!v.paused&&v.readyState<2)};
}
function distanceAt(rows,t,media={}) {
 const row=rows.filter(r=>r.t<=t+1e-9).at(-1);
 const empty=reason=>({status:'측정 불가',wait:'측정 불가',reached_m:null,tail:null,held:false,stability:'측정 불가',reason});
 if(!row){const d=distanceWaiting();if(media.ended){d.stability='재생 종료';d.reason='재생 종료 · 유효 대기정보 없음';}return d;}
 const d={...row.distance},measured=d.last_valid_time_s;
 if(d.reached_m==null){if(media.ended){d.stability='재생 종료';d.reason='재생 종료 · 유효 대기정보 없음';}return d;}
 if(measured==null||!Number.isFinite(t)||t<measured-1e-9)return empty('현재 영상 시각 이전의 유효 판정이 없습니다.');
 const age=t-measured;
 if(d.retain_last){
  d.held=!!d.held||age>1.1+1e-9||!!media.failed||!!media.delayed;
  d.hold_age_s=Math.max(0,age);d.stability=media.ended?'재생 종료':d.held?'갱신 지연':'유효 관측';
  if(media.ended)d.reason='재생 종료 · 마지막 정상 갱신 영상 시각 '+measured.toFixed(2)+'초';
  else if(d.held)d.reason='갱신 지연 · 마지막 정상 갱신 영상 시각 '+measured.toFixed(2)+'초 · '+(d.pending_change||d.raw_reason||'새 관측 없음');
  return d;
 }
 if(age>3+1e-9)return empty('마지막 유효 관측 이후 3초 초과 · '+(d.raw_reason||''));
 d.held=!!d.held||age>1.1+1e-9;d.hold_age_s=Math.max(0,age);d.stability=d.held?'최근 판정 유지':'유효 관측';
 if(d.held)d.reason='최근 판정 유지 · 마지막 유효 관측 '+measured.toFixed(2)+'초 · 경과 '+age.toFixed(2)+'초 · '+(d.pending_change||d.raw_reason||'새 관측 없음');
 return d;
}
function distanceStatus(d) {
 const queue=d?.display_values?.queue;
 if(d?.reached_m!=null){
  if(typeof queue==='number'&&Number.isFinite(queue)&&queue===0)return '대기없음';
  if(d.overflow)return '매우 혼잡';
  const match=String(d.wait||'').match(/^([0-9]+)분 (미만|이상)$/);
  if(match){const minutes=Number(match[1]);if(match[2]==='미만')return minutes<=5?'여유':minutes<=10?'보통':minutes<=15?'혼잡':'매우 혼잡';return minutes>=15?'매우 혼잡':minutes>=10?'혼잡':minutes>=5?'보통':'여유';}
 }
 return d?.status||'측정 불가';
}
function distanceState(record) {
 const state=distanceStatus(distanceValue(record));
 const colors={'대기없음':['#0284c7','blue'],'여유':['#008b6a','green'],'보통':['#c28a00','yellow'],'혼잡':['#dc2626','red'],'매우 혼잡':['#991b1b','darkred'],'화면 범위 초과':['#991b1b','darkred']};
 const [color,cls]=colors[state]||['#8393a5','gray'];return [distanceStatus(distanceValue(record)),color,cls];
}
function recommendDistance(current,vals,cfg) {
 const rooms=Object.keys(vals);
 if(rooms.some(r=>!Number.isFinite(distanceRank(distanceValue(vals[r])))))return null;
 const band=r=>distanceValue(vals[r]).reached_m;
 const alternatives=rooms.filter(r=>r!==current&&band(r)<band(current));
 alternatives.sort((a,b)=>band(a)-band(b)||cfg.walk[current][a]-cfg.walk[current][b]);
 return alternatives[0]||null;
}
function distanceRank(d){return d.held||d.overflow||d.reached_m==null?Infinity:d.reached_m;}
function totalWaitLabel(d,walkSeconds){return d.wait_lower_bound_minutes==null?null:(d.wait_lower_bound_minutes+walkSeconds/60)+'분 이상';}
function paintDistance(root, value, overlay) {
 if(!root)return;
 const d=value||distanceWaiting();
 for(const k of ['status','wait','reason'])root.querySelector('[data-distance="'+k+'"]').textContent=k==='status'?distanceStatus(d):d[k];
 root.querySelector('[data-distance="stability"]').textContent=d.stability||(d.reached_m==null?'측정 불가':'유효 관측');
 root.querySelector('[data-distance="reach"]').textContent=d.overflow?'10m 초과 · 지정된 화면 경계 접촉':d.reached_m==null?'도달 기준선: 측정 불가':d.reached_m===0?'도달 기준선: 없음 (5m 미만)':'도달 기준선: '+d.reached_m+'m';
 const updated=root.querySelector('[data-distance="updated"]');
 if(updated)updated.textContent=d.last_valid_time_s==null?'마지막 정상 갱신: 없음':'마지막 정상 갱신: '+new Date((14*3600+d.last_valid_time_s)*1000).toISOString().slice(11,19)+(root.dataset?.compact==='true'?'':' (영상 '+d.last_valid_time_s.toFixed(2)+'초)');
 const assumption=root.querySelector('[data-distance="assumption"]');
 if(assumption)assumption.textContent=root.dataset?.compact==='true'?(d.overflow?'시연 추정 · 범위 초과 MVP 가정':'시연 추정'):d.overflow?'시연 추정 · 대기 15분 이상(MVP)':'임의 거리 기준 시연값';
 const tail=overlay?.querySelector('[data-tail]');
 if(tail){tail.setAttribute('visibility',d.tail?'visible':'hidden');tail.setAttribute('opacity',d.held?'.5':'1');if(d.tail){tail.setAttribute('cx',d.tail[0]*1000);tail.setAttribute('cy',d.tail[1]*1000);}}
 const label=overlay?.querySelector('[data-tail-label]');
 if(label){label.setAttribute('visibility',d.tail&&d.tail_kind?'visible':'hidden');if(d.tail){label.setAttribute('x',Math.min(780,d.tail[0]*1000+12));label.setAttribute('y',Math.max(25,d.tail[1]*1000-12));label.textContent=(d.tail_kind||'')+(d.tail_track_id!=null?' #'+d.tail_track_id:'');}}
}
'''


def reach_label(result):
    reached=result.get('reached_m')
    if result.get('overflow'):return '10m 초과 · 지정된 화면 경계 접촉'
    return '도달 기준선: 측정 불가' if reached is None else ('도달 기준선: 없음 (5m 미만)' if reached == 0 else f'도달 기준선: {reached}m')
