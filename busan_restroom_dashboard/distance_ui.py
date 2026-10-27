"""Mouse-only line editor; no adjustable distances or waiting-time thresholds."""
import base64
import hashlib
import io
import json
from pathlib import Path
import streamlit as st
from distance_demo import BANDS, DISCLAIMER, validate_lines, video_key

_EDITOR = st.components.v2.component(
    'restroom_distance_lines',
    html='''<div class="toolbar"><button data-mode="origin">시작점</button><button data-mode="5">5m 선</button><button data-mode="10">10m 선</button><button data-mode="15">15m 선</button><button data-clear>모두 다시 지정</button><button data-save>이 CCTV 기준선 저장</button></div><p role="status" aria-live="polite"></p><canvas aria-label="시작점과 거리 기준선을 마우스로 지정하는 영상" style="width:100%;height:auto;display:block;touch-action:none"></canvas>''',
    css='''
    .toolbar{display:flex;gap:8px;flex-wrap:wrap}
    button{padding:8px 12px;border-radius:6px;border:1px solid var(--st-border-color);background:var(--st-secondary-background-color);color:var(--st-text-color);cursor:pointer}
    button[aria-pressed=true]{outline:2px solid var(--st-primary-color)}
    button:disabled{opacity:.5;cursor:default}p{font-size:14px;color:var(--st-text-color)}
    ''',
    js=(Path(__file__).parent/'distance_editor.js').read_text(encoding='utf-8'))


@st.cache_data(show_spinner=False)
def video_duration(source, signature):
    import av
    with av.open(source) as container:
        stream = container.streams.video[0]
        return float(stream.duration*stream.time_base) if stream.duration is not None else float(container.duration or 0)/av.time_base


@st.cache_data(show_spinner=False)
def reference_frame(source, signature, seconds):
    import av
    with av.open(source) as container:
        stream = container.streams.video[0]
        container.seek(int(seconds/float(stream.time_base)), stream=stream)
        for frame in container.decode(stream):
            if frame.time is not None and frame.time + .05 < seconds:
                continue
            image = frame.to_image()
            original = image.size
            image.thumbnail((1280, 900))
            out = io.BytesIO(); image.save(out, format='JPEG')
            return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode(), original
    raise ValueError('지정 시점의 영상 프레임을 읽을 수 없습니다.')


def render_distance_settings(cfg, save_settings, disabled=False):
    st.subheader('CCTV별 5m·10m·15m 기준선')
    st.caption(DISCLAIMER+' · 실제 거리 측정값이 아닙니다. 후보자는 대기 ROI 안에서 연속 2초 저속 체류 또는 확정 대기줄과 동반 이동한 근거가 있을 때만 거리 분석에 포함합니다. 기존 인원 카운팅은 바뀌지 않습니다. 시작점에서 대기줄이 길어지는 방향으로 선을 지정하고 각 선은 대기줄 전체 폭을 가로질러야 합니다. 굽은 줄이나 가림으로 판정이 어려우면 측정 불가로 표시합니다.')
    st.table({'지정 기준': ['5m 미만', '5m 이상 ~ 10m 미만', '10m 이상 ~ 15m 미만', '15m 이상'],
              '혼잡도': ['여유', '보통', '혼잡', '매우 혼잡'],
              '예상 대기시간': [band[2] for band in BANDS]})
    from distance_reference import shared_editor_hidden
    if shared_editor_hidden(cfg):
        st.caption('세 CCTV 원본과 공통 기준선이 일치합니다. 기준선은 영상 위에 계속 표시됩니다.')
        return
    room = st.radio('기준선을 지정할 CCTV', ['north', 'east', 'south'],
                    format_func=lambda r: {'north':'북쪽','east':'동쪽','south':'남쪽'}[r],
                    horizontal=True, key='distance_room', disabled=disabled)
    source = cfg['videos'].get(room, '')
    signature = video_key(source)
    setting = cfg.get('distance_demo', {}).get(room, {})
    image, size, seconds = '', (960, 540), 0.
    if signature:
        try:
            duration = video_duration(source, signature)
            if duration > .1:
                seconds = st.slider('기준선 지정에 사용할 영상 시점 · 초', 0., max(0., duration-.1), 0., .1, key='distance_frame_'+room)
            image, size = reference_frame(source, signature, seconds)
        except Exception as exc:
            st.error('영상 프레임을 읽을 수 없습니다: '+str(exc))
            return
    else:
        st.info('연결된 CCTV 원본 영상이 없습니다. 아래 격자에서 지정 연습을 할 수 있습니다. 연습 기준선은 실제 영상 결과에 적용되지 않습니다. 영상을 연결한 뒤 해당 영상 위에 다시 저장하세요.')
    if setting and setting.get('source_key') != signature:
        st.warning('저장된 기준선과 현재 영상이 다릅니다. 현재 영상에서 다시 지정하세요.')
    usable = setting if setting.get('source_key') == signature else {}
    revision = hashlib.sha256(json.dumps(usable, sort_keys=True).encode()).hexdigest()[:12]
    result = _EDITOR(data={'setting': usable, 'image': image, 'width':size[0], 'height':size[1],
                           'source_key':signature, 'disabled':disabled},
                     key=f'distance-editor-{room}-{signature or "draft"}-{seconds}-{revision}',
                     on_apply_change=lambda: None)
    payload = result.apply
    if payload and not disabled:
        issue = validate_lines(payload)
        if payload.get('source_key') != signature:
            issue = '영상이 변경되었습니다. 현재 영상에서 다시 지정하세요.'
        if issue:
            st.error(issue)
        else:
            updated = json.loads(json.dumps(cfg))
            updated.setdefault('distance_demo', {})[room] = {
                'origin':payload['origin'], 'lines':payload['lines'],
                'source_key':signature, 'frame_s':seconds, 'label':DISCLAIMER}
            save_settings(updated)
            st.session_state['distance_saved_message'] = ('연습용 ' if not signature else '')+'기준선을 저장했습니다. · '+DISCLAIMER
            st.rerun()
    if message := st.session_state.pop('distance_saved_message', None):
        st.success(message)
    if usable:
        st.caption('저장 상태: '+('현재 영상 연결됨' if signature else '영상 없는 연습용')+' · '+DISCLAIMER)
