"""Shared distance-only presentation for existing playback views."""
import html
from distance_demo import DISCLAIMER, unavailable, settings_for


def panel(result=None, element_id='distance-result'):
    result = result or unavailable('이 시점의 거리 분석 기록이 없습니다.')
    esc = lambda x: html.escape(str(x), quote=True)
    reached = result.get('reached_m')
    reach = '도달 기준선: 측정 불가' if reached is None else ('도달 기준선: 없음 (5m 미만)' if reached == 0 else f'도달 기준선: {reached}m')
    stability=result.get('stability','측정 불가' if reached is None else '유효 관측')
    return f'''<section id="{esc(element_id)}" class="distance-demo" aria-live="polite" style="padding:12px;border-top:1px solid #d6e1eb;background:#f5f8fc;line-height:1.7"><strong>거리 기준 혼잡도 · <span data-distance="status">{esc(result['status'])}</span></strong><div>예상 대기시간: <b data-distance="wait">{esc(result['wait'])}</b></div><strong data-distance="stability">{esc(stability)}</strong><div data-distance="reach">{esc(reach)}</div><small data-distance="reason">{esc(result['reason'])}</small><div style="font-size:11px;color:#566b80">{DISCLAIMER}</div></section>'''


def overlay(cfg, room):
    setting, key = settings_for(cfg, room)
    if not key or setting.get('source_key') != key:
        return ''
    from distance_demo import validate_lines
    if validate_lines(setting):
        return ''
    shapes = []
    for m, color in [('5','#59b2ff'),('10','#ffcc54'),('15','#ff627d')]:
        a,b=setting['lines'][m]
        shapes.append(f'<line x1="{a[0]*1000}" y1="{a[1]*1000}" x2="{b[0]*1000}" y2="{b[1]*1000}" stroke="{color}" stroke-width="4"/><text x="{(a[0]+b[0])*500}" y="{(a[1]+b[1])*500-8}" fill="{color}" font-size="24">{m}m</text>')
    return f'''<svg id="distance-overlay-{room}" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="임의 거리 기준 시연선과 마지막 대기자 위치" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none">{''.join(shapes)}<circle data-tail r="9" fill="#fff" stroke="#e34822" stroke-width="4" visibility="hidden"/><text data-tail-label font-size="20" fill="#fff" stroke="#172431" stroke-width=".4" visibility="hidden"/></svg>'''


def script():
    return '''
function distanceValue(record) {
 return record?.distance||{status:'측정 불가',wait:'측정 불가',reached_m:null,reason:'이 시점의 거리 분석 기록이 없습니다.'};
}
function distanceAt(rows,t) {
 const row=rows.filter(r=>r.t<=t+1e-9).at(-1);
 const empty=reason=>({status:'측정 불가',wait:'측정 불가',reached_m:null,tail:null,held:false,stability:'측정 불가',reason});
 if(!row)return empty('이 시점의 거리 분석 기록이 없습니다.');
 const d={...row.distance},measured=d.last_valid_time_s;
 if(d.reached_m==null)return d;
 if(measured==null||!Number.isFinite(t)||t<measured-1e-9)return empty('현재 영상 시각 이전의 유효 판정이 없습니다.');
 const age=t-measured;
 if(age>3+1e-9)return empty('마지막 유효 관측 이후 3초 초과 · '+(d.raw_reason||''));
 d.held=!!d.held||age>1.1+1e-9;d.hold_age_s=Math.max(0,age);d.stability=d.held?'최근 판정 유지':'유효 관측';
 if(d.held)d.reason='최근 판정 유지 · 마지막 유효 관측 '+measured.toFixed(2)+'초 · 경과 '+age.toFixed(2)+'초 · '+(d.pending_change||d.raw_reason||'새 관측 없음');
 return d;
}
function distanceState(record) {
 const state=distanceValue(record).status;
 const colors={'여유':['#008b6a','green'],'보통':['#c28a00','yellow'],'혼잡':['#d7413e','red'],'매우 혼잡':['#8e1b40','red']};
 const [color,cls]=colors[state]||['#8393a5','gray'];return [state,color,cls];
}
function recommendDistance(current,vals,cfg) {
 const rooms=Object.keys(vals);
 if(rooms.some(r=>distanceValue(vals[r]).reached_m==null))return null;
 const band=r=>distanceValue(vals[r]).reached_m;
 const alternatives=rooms.filter(r=>r!==current&&band(r)<band(current));
 alternatives.sort((a,b)=>band(a)-band(b)||cfg.walk[current][a]-cfg.walk[current][b]);
 return alternatives[0]||null;
}
function paintDistance(root, value, overlay) {
 if(!root)return;
 const d=value||{status:'측정 불가',wait:'측정 불가',reached_m:null,reason:'이 시점의 거리 분석 기록이 없습니다.'};
 for(const k of ['status','wait','reason'])root.querySelector('[data-distance="'+k+'"]').textContent=d[k];
 root.querySelector('[data-distance="stability"]').textContent=d.stability||(d.reached_m==null?'측정 불가':'유효 관측');
 root.querySelector('[data-distance="reach"]').textContent=d.reached_m==null?'도달 기준선: 측정 불가':d.reached_m===0?'도달 기준선: 없음 (5m 미만)':'도달 기준선: '+d.reached_m+'m';
 const tail=overlay?.querySelector('[data-tail]');
 if(tail){tail.setAttribute('visibility',d.tail?'visible':'hidden');tail.setAttribute('opacity',d.held?'.5':'1');if(d.tail){tail.setAttribute('cx',d.tail[0]*1000);tail.setAttribute('cy',d.tail[1]*1000);}}
 const label=overlay?.querySelector('[data-tail-label]');
 if(label){label.setAttribute('visibility',d.tail&&d.tail_kind?'visible':'hidden');if(d.tail){label.setAttribute('x',Math.min(780,d.tail[0]*1000+12));label.setAttribute('y',Math.max(25,d.tail[1]*1000-12));label.textContent=(d.tail_kind||'')+(d.tail_track_id!=null?' #'+d.tail_track_id:'');}}
}
'''
