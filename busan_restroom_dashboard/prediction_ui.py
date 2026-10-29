"""Per-restroom prediction uploads and portable, validated persistence."""
from datetime import datetime
import pandas as pd
from prediction_csv import (load_predictions, merge_predictions, save_predictions,
                            resolve_prediction_path, ROOM_IDS, DISTANCES, WAITS)


def render_prediction_registration(cfg, save_settings):
    import streamlit as st
    from core import ROOMS
    st.caption('북쪽 A · 신관 B · 남쪽 C에 각각 파일을 올리세요. CSV·XLSX·XLS를 지원하며 엑셀은 첫 번째 시트를 읽습니다.')
    st.info('날짜·시간·예상 대기거리 구간이 있으면 됩니다. 화장실ID는 업로드한 칸에 맞춰 자동으로 넣고, 대기시간은 거리 구간에서 자동 계산합니다.')
    current=None
    if cfg.get('prediction_csv_path'):
        try:current=load_predictions(resolve_prediction_path(cfg['prediction_csv_path']))
        except (OSError,ValueError,UnicodeError) as error:
            st.warning('이전 예측 연결을 읽지 못했습니다. 아래에서 파일을 다시 등록하면 연결을 복구합니다.')
            with st.expander('이전 파일 오류 내용'):st.write(str(error))
    replacements={};invalid=False
    for col,room in zip(st.columns(3),ROOMS):
        with col:
            st.subheader(f'{ROOMS[room]} · {ROOM_IDS[room]}')
            candidate=st.file_uploader(f'{ROOMS[room]} 예측 파일',type=['csv','xlsx','xls'],key='prediction_room_upload_'+room)
            if candidate is not None:
                try:
                    frame=load_predictions(candidate.getvalue(),room=room,filename=candidate.name)
                    replacements[room]=frame
                    st.success(f"{len(frame):,}행 · ID 자동 지정 완료")
                    st.caption(f"{frame['시각'].min()} ~ {frame['시각'].max()}")
                    st.dataframe(frame.head(5),hide_index=True,width='stretch')
                except (OSError,ValueError,UnicodeError) as error:
                    invalid=True;st.error(str(error))
            elif current is not None:
                count=int((current['화장실ID']==ROOM_IDS[room]).sum())
                st.caption(f'등록됨: {count:,}행' if count else '미등록')
    st.caption('한 곳씩 등록해도 됩니다. 다시 올린 화장실의 기록만 교체하며, 나머지 화장실 기록은 유지합니다. 시간의 초는 해당 분의 00초로 맞춥니다.')
    align=st.checkbox('적용 시 CCTV 시연 날짜를 예측 파일 날짜에 자동으로 맞추기',value=True,key='prediction_align_day')
    if st.button('업로드한 예측 적용',type='primary',disabled=not replacements or invalid):
        try:
            merged=merge_predictions(current,replacements)
            cfg['prediction_csv_path']=save_predictions(merged)
            if align:
                days=sorted({day for frame in replacements.values() for day in frame['날짜'].unique()})
                cfg['capture_date']=cfg['capture_date'] if cfg.get('capture_date') in days else days[0]
                st.session_state['prediction_day_editor']=datetime.fromisoformat(cfg['capture_date']).date()
            save_settings(cfg)
            st.session_state['_prediction_upload_saved']=True
            st.rerun()
        except (OSError,ValueError,UnicodeError) as error:st.error('예측을 저장하지 못했습니다: '+str(error))
    if st.session_state.pop('_prediction_upload_saved',False):st.success('예측을 저장했습니다. 사이니지에서 날짜·시간에 맞춰 자동으로 조회합니다.')
    if current is not None:
        st.subheader('적용 중인 예측')
        summary=current.groupby('화장실ID').agg(행수=('시각','size'),시작=('시각','min'),종료=('시각','max')).reset_index()
        st.dataframe(summary,hide_index=True,width='stretch')
        st.download_button('자동 변환된 통합 CSV 다운로드',current.to_csv(index=False).encode('utf-8-sig'),'restroom_predictions.csv','text/csv')
    if cfg.get('prediction_csv_path') and st.button('전체 예측 연결 해제'):
        cfg.pop('prediction_csv_path',None);save_settings(cfg);st.rerun()
    with st.expander('거리 구간별 자동 변환 기준'):
        st.table(pd.DataFrame({'예상 대기거리 구간':DISTANCES,'예상 대기시간 (거리 환산)':WAITS}))
    day=st.date_input('CCTV 시연 날짜',value=datetime.fromisoformat(cfg['capture_date']).date(),key='prediction_day_editor')
    if st.button('시연 날짜 적용'):
        cfg['capture_date']=day.isoformat();save_settings(cfg);st.rerun()
    st.caption('파일에 있는 날짜와 시간을 보존합니다. 같은 분의 예측만 조회하며, 예측이 없는 날짜·시간은 정보 없음으로 표시합니다. 영상 시작 시각은 선택한 날짜 14:00:00입니다.')
