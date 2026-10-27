import pandas as pd
import streamlit as st
from preprocess import parse_ktx, parse_regular, expand_dates
from datetime import date
from io import BytesIO
from database import check_connection, save_records


def render_train_registration():
    st.caption('두 형식은 각각 업로드하면 공통 컬럼으로 자동 통합됩니다. 한 종류만 올려도 됩니다.')
    with st.expander('MySQL 연결 설정', expanded=True):
        st.header('MySQL 연결')
        db_host = st.text_input('호스트', value='127.0.0.1')
        db_port = st.number_input('포트', min_value=1, max_value=65535, value=3306, step=1)
        db_name = st.text_input('데이터베이스', value='railway_system')
        db_user = st.text_input('사용자', value='root')
        db_password = st.text_input('MySQL 비밀번호', type='password')
        db_config = dict(host=db_host, port=int(db_port), database=db_name,
                         user=db_user, password=db_password)
        st.caption('Workbench에 연결할 때 쓰는 MySQL 비밀번호를 입력하세요.')
        if st.button('DB 연결 확인'):
            try:
                version = check_connection(db_config)
                st.success(f'연결 성공 · MySQL {version} · 열차 테이블 확인 완료')
            except Exception as error:
                code = getattr(error, 'errno', None)
                if code == 1045:
                    st.error('로그인 실패: MySQL 사용자와 비밀번호를 확인하세요.')
                elif code in (2002, 2003):
                    st.error('서버에 연결할 수 없습니다. MySQL 실행 상태·호스트·포트를 확인하세요.')
                else:
                    st.error(f'연결 오류: {error}')

    ktx_file = st.file_uploader('KTX 시간표 업로드', type=['xlsx'], key='ktx')
    regular_file = st.file_uploader('일반열차 시간표 업로드 (ITX·무궁화)', type=['xlsx'], key='regular')
    if ktx_file is not None or regular_file is not None:
        try:
            frames, raw_sources, signatures = [], [], []
            for label, file, parser in [('KTX', ktx_file, parse_ktx), ('일반열차', regular_file, parse_regular)]:
                if file is None:
                    continue
                excel = pd.ExcelFile(BytesIO(file.getvalue()))
                if '경부선' not in excel.sheet_names:
                    raise ValueError(f'{file.name}: 경부선 시트가 없습니다.')
                raw = pd.read_excel(excel, sheet_name='경부선', header=None)
                parsed = parser(raw)
                frames.append(parsed)
                raw_sources.append((file.name, raw))
                signatures.append((label, file.getvalue()))
                st.write(f'{label}: {len(parsed)}개 기록 추출')
            from preprocess import COLUMNS
            all_records = pd.concat(frames, ignore_index=True)
            result = all_records.drop_duplicates(subset=COLUMNS).sort_values(
                ['예정시각','운행구분','열차번호']).reset_index(drop=True)
            st.subheader('부산역 통합 시간표')
            st.success(f"도착 {(result['운행구분'] == '도착').sum()}개 · 출발 {(result['운행구분'] == '출발').sum()}개 · 총 {len(result)}개 시간표 기록")
            st.dataframe(result, hide_index=True)
            st.caption('예정 시간표 기록입니다. 날짜별 실제 운행 편수와는 다릅니다. 일자오프셋 1은 출발 다음 날 부산역 도착을 뜻합니다.')
            st.info('비고 빈칸은 매일 운행, 요일 표기는 해당 출발요일만 운행하는 조건입니다. 시행 기간이 다른 시간표는 함께 올리지 마세요.')
            if (result['운행요일'] == '확인필요').any():
                st.warning('운행요일 확인이 필요한 기록이 있습니다.')
            st.download_button('전처리 결과 CSV 다운로드', result.to_csv(index=False).encode('utf-8-sig'),
                               '부산역_열차시간표.csv', 'text/csv')
            st.subheader('날짜별 운행요일 매칭')
            st.caption('부산역에 도착하거나 출발하는 날짜의 범위를 선택하세요. 시간표가 이 기간에 유효한지 확인 후 사용하세요.')
            with st.form('date_matching'):
                start_date = st.date_input('시작일', value=date.today())
                end_date = st.date_input('종료일', value=date.today())
                generate = st.form_submit_button('날짜별 기록 생성')
            signature = tuple(signatures)
            if st.session_state.get('matching_signature') != signature:
                st.session_state.pop('matched_records', None)
            if generate:
                st.session_state.pop('matched_records', None)
                matched = expand_dates(result, start_date, end_date)
                matched = matched.drop_duplicates(subset=['날짜','열차번호','열차종류','운행구분','예정시각','열차출발일']).reset_index(drop=True)
                st.session_state['matched_records'] = matched
                st.session_state['matching_signature'] = signature
                st.session_state['matching_period'] = (start_date, end_date)
            if 'matched_records' in st.session_state:
                matched = st.session_state['matched_records']
                a, b = st.session_state['matching_period']
                st.success(f'{a} ~ {b}: 총 {len(matched)}개 예정 운행 기록')
                st.dataframe(matched, hide_index=True)
                st.caption('요일번호는 월요일 0 ~ 일요일 6. 익일 도착은 전날 열차출발일의 운행조건으로 판단합니다. 공휴일 특별운행·운휴는 별도 자료가 필요합니다.')
                st.download_button('날짜별 기록 CSV 다운로드', matched.to_csv(index=False).encode('utf-8-sig'),
                                   '부산역_날짜별_열차기록.csv', 'text/csv')
                st.subheader('MySQL에 저장')
                st.caption('위에 표시된 날짜별 기록을 저장합니다. 같은 날짜·열차번호·운행구분·예정시각은 건너뜁니다. 예정시각 변경은 별도 기록으로 저장되므로 시간표 개정 시 기존 기록을 확인하세요.')
                if st.button('날짜별 기록 DB 저장', disabled=matched.empty):
                    try:
                        with st.spinner('열차기록 저장 중…'):
                            saved = save_records(matched, db_config)
                        st.success(f"저장 완료: 신규 {saved['inserted']:,}건 · 중복 건너뛰기 {saved['skipped']:,}건")
                        st.info('도착시각·출발시각·지연시간·승강장번호는 실시간 데이터 확보 전까지 NULL로 남습니다.')
                    except Exception as error:
                        st.error(f'DB 저장 실패: {error}')
                        st.caption('이번 작업의 신규 저장은 취소됐습니다. 연결 정보와 기존 테이블을 확인하세요.')
            for filename, source in raw_sources:
                with st.expander(f'원본 데이터: {filename}'):
                    view = source.fillna('').astype(str)
                    from openpyxl.utils import get_column_letter
                    view.columns = [get_column_letter(i + 1) for i in range(len(view.columns))]
                    view.index = range(1, len(view) + 1)
                    st.dataframe(view, height=600)
        except Exception as error:
            st.session_state.pop('matched_records', None)
            st.error(f'파일 처리 오류: {error}')
