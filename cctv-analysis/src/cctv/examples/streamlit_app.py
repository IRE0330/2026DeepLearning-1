"""Minimal local adapter: python -m streamlit run <this file>."""
# Windows spawn re-imports the main script as __mp_main__; never run UI there.
if __name__ == "__main__":
    import os
    from pathlib import Path
    import uuid
    import streamlit as st
    from cctv import AnalysisService, BusyError

    st.set_page_config(page_title='CCTV 분석 모듈 호출 예시')
    st.title('단일 영상 분석 호출 예시')
    st.caption('시연 가정 · 수동 정확도 미검증 · 실제 CCTV/예측모델 미연동')


    @st.cache_resource(max_entries=1)
    def get_service():
        # Shared across sessions in THIS Streamlit server process. No UI calls in workers.
        return AnalysisService(lease_seconds=90, stop_timeout=10)


    service = get_service()
    st.session_state.setdefault('analysis_owner', uuid.uuid4().hex)
    owner = st.session_state['analysis_owner']
    current = service.status(owner)
    active = current.get('worker_alive', False)

    with st.form('analysis_request'):
        room = st.selectbox('화장실', ['north', 'south', 'east'], key='room')
        video = st.text_input('영상 경로 (서버의 로컬 파일)', value=os.getenv('CCTV_EXAMPLE_VIDEO', ''), key='video')
        model = st.text_input('가중치 경로 (yolo11n.pt)', value=os.getenv('CCTV_EXAMPLE_MODEL', ''), key='model')
        output = st.text_input('결과 저장 폴더', value=os.getenv('CCTV_EXAMPLE_OUTPUT', str(Path.cwd() / 'outputs')), key='output')
        device = st.selectbox('실행 장치', ['cpu', 'cuda:0'], key='device')
        end = st.number_input('검증용 종료 초 (0이면 전체)', min_value=0., value=0., step=1., key='end')
        submitted = st.form_submit_button('분석 시작', disabled=active)
        if submitted:
            try:
                if not video.strip() or not model.strip() or not output.strip():
                    raise ValueError('영상·가중치·결과 경로를 모두 입력하세요.')
                service.start(owner=owner, restroom_id=room, video_path=video, model_path=model,
                              output_dir=output, device=device, profile='demo', end=end or None)
                st.rerun()
            except (ValueError, OSError, BusyError) as exc:
                st.error(str(exc))


    @st.fragment(run_every=1)
    def show_status():
        status = service.status(owner)
        alive = status.get('worker_alive', False)
        prior_alive = st.session_state.get('prior_worker_alive')
        st.session_state['prior_worker_alive'] = alive
        if prior_alive is True and not alive:
            st.rerun()  # Refresh the form's disabled state after the worker actually exits.
        label = {'idle': '대기', 'preparing': '준비', 'running': '분석 중', 'stopping': '중지 요청 중',
                 'stopped': '중지 완료', 'completed': '정상 완료', 'failed': '실패',
                 'force_terminated': '제한시간 초과 강제 종료'}.get(status['status'], status['status'])
        st.text('상태: ' + label)
        if alive and not status['owned_by_session']:
            st.info('다른 세션이 분석 중입니다. 완료 또는 소유 세션의 중지를 기다리세요.')
        if status.get('progress') is not None:
            st.progress(status['progress'], text=f"처리 프레임: {status['processed_frames']}")
        runtime = status.get('runtime_device')
        st.text('실제 추론 장치: ' + (str(runtime['parameter_device']) if runtime else '아직 확인 전'))
        if status.get('error'):
            st.error(status['error'])
        if st.button('분석 중지', disabled=not (alive and status['owned_by_session']), key='stop'):
            service.stop(owner, wait=False)
            st.rerun()
        latest = status.get('latest_record')
        if latest is not None:
            st.caption(f"최신 기록: 영상 {latest['interval_end_s']:.3f}초 · 저장 {latest['persisted_at']}")
            st.json(latest['csv_row'])
            st.json({'expected_wait_s': latest['detail']['state'].get('expected_wait_s'),
                     'record_id': latest['record_id'], 'is_demo': latest['is_demo']})
        else:
            st.caption('아직 저장된 정기 레코드가 없습니다.')
        if status.get('job_dir'):
            st.code(status['job_dir'], language=None)
        for item in status.get('csv_files', []):
            st.code(item['path'], language=None)


    show_status()
    st.caption('조회는 약1초 주기이며 실제 데이터 도착 주기를 보장하지 않습니다. 연결 종료 후90초 동안 소유 세션의 조회가 없으면 중지를 요청합니다.')
