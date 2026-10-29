"""제공된 KTX·일반열차 경부선 시간표에서 부산역 예정 이벤트 추출."""
import datetime as dt
import numbers
import re
import pandas as pd

COLUMNS = ['열차번호', '열차종류', '운행구분', '예정시각', '운행요일', '부산역_일자오프셋']

def operating_days(value):
    text = clean(value)
    if not text or text == '매일':
        return set(range(7))
    text = text.replace('요일', '')
    text = re.sub(r'[\s,·/ㆍ및]', '', text)
    if not text or any(char not in '월화수목금토일' for char in text):
        raise ValueError(f'해석할 수 없는 운행요일: {value}. 원본을 확인하세요.')
    return {'월화수목금토일'.index(char) for char in text}

def expand_dates(timetable, start_date, end_date):
    """선택 기간은 부산역 이벤트 날짜 기준. 출발일의 요일 조건을 확인한다."""
    if end_date < start_date:
        raise ValueError('종료일은 시작일보다 빠를 수 없습니다.')
    rows = []
    prepared = [(row, operating_days(row['운행요일']))
                for row in timetable.to_dict('records')]
    current = start_date
    while current <= end_date:
        for row, days in prepared:
            departure_date = current - dt.timedelta(days=int(row['부산역_일자오프셋']))
            if departure_date.weekday() not in days:
                continue
            time = dt.time.fromisoformat(row['예정시각'])
            rows.append({
                '날짜': current.isoformat(),
                '요일': '월화수목금토일'[current.weekday()] + '요일',
                '요일번호': current.weekday(),
                '주말여부': int(current.weekday() >= 5),
                '열차번호': row['열차번호'],
                '열차종류': row['열차종류'],
                '운행구분': row['운행구분'],
                '예정시각': row['예정시각'],
                '예정일시': dt.datetime.combine(current, time).isoformat(sep=' '),
                '운행요일': row['운행요일'],
                '열차출발일': departure_date.isoformat()
            })
        current += dt.timedelta(days=1)
    columns = ['날짜','요일','요일번호','주말여부','열차번호','열차종류','운행구분','예정시각','예정일시','운행요일','열차출발일']
    return pd.DataFrame(rows, columns=columns).sort_values(
        ['예정일시','운행구분','열차번호']).reset_index(drop=True)

def clean(value):
    return re.sub(r'\s+', '', str(value)) if pd.notna(value) else ''

def valid_time(value):
    return isinstance(value, dt.time) and value != dt.time(0, 0)

def number(value):
    if isinstance(value, numbers.Real) and pd.notna(value):
        return str(int(value)) if float(value).is_integer() else ''
    text = clean(value)
    return text if text.isdigit() else ''

def offset(values):
    previous, days = None, 0
    for value in values:
        if not valid_time(value):
            continue
        if previous is not None and value < previous:
            days += 1
        previous = value
    return days

def weekday(value, blank_is_daily=True):
    if pd.isna(value) or isinstance(value, dt.time):
        return '매일' if blank_is_daily else '확인필요'
    text = clean(value)
    return text or ('매일' if blank_is_daily else '확인필요')

def record(tid, kind, event, time, note, days):
    return dict(zip(COLUMNS, [tid, kind, event, time.strftime('%H:%M:%S'), note, days]))

def finish(records):
    if not records:
        raise ValueError('부산역 기록을 찾지 못했습니다. 파일 형식과 경부선 시트를 확인하세요.')
    return pd.DataFrame(records, columns=COLUMNS).sort_values(
        ['예정시각', '운행구분', '열차번호']).reset_index(drop=True)

def parse_ktx(raw):
    candidates = [i for i, row in raw.iterrows()
                  if '열차번호' in row.tolist() and '부산' in row.tolist()]
    if not candidates:
        raise ValueError('KTX 양식이 아닙니다. 시간표 형식을 다시 선택하세요.')
    header = candidates[0]
    labels = raw.loc[header].tolist()
    starts = [i for i, value in enumerate(labels) if value == '열차번호']
    records = []
    for j, start in enumerate(starts):
        end = starts[j + 1] if j + 1 < len(starts) else len(labels)
        stations = [i for i in range(start + 2, end)
                    if isinstance(labels[i], str) and not labels[i].startswith('비고')]
        busan = [i for i in stations if labels[i] == '부산']
        if len(busan) != 1:
            continue
        col = busan[0]
        if col == stations[0]:
            event = '출발'
        elif col == stations[-1]:
            event = '도착'
        else:
            raise ValueError('부산역이 중간역인 시간표는 지원하지 않습니다.')
        note_col = next((i for i in range(start, end)
                         if isinstance(labels[i], str) and labels[i].startswith('비고')), None)
        for _, row in raw.loc[header + 1:].iterrows():
            tid, time = number(row.iloc[start]), row.iloc[col]
            if not tid or not valid_time(time):
                continue
            note = weekday(row.iloc[note_col]) if note_col is not None else '확인필요'
            days = offset([row.iloc[c] for c in stations if c <= col])
            records.append(record(tid, row.iloc[start + 1], event, time, note, days))
    return finish(records)

def parse_regular(raw):
    labels = [clean(value) for value in raw.iloc[:, 0]]
    starts = [i for i, label in enumerate(labels) if label.startswith('경부선')
              and ('하행' in label or '상행' in label)]
    if not starts:
        raise ValueError('일반열차 양식이 아닙니다. 시간표 형식을 다시 선택하세요.')
    records = []
    for j, start in enumerate(starts):
        end = starts[j + 1] if j + 1 < len(starts) else len(raw)
        def find(label):
            return next((i for i in range(start, end) if labels[i] == label), None)
        id_row, kind_row, busan_row, note_row = [find(x) for x in ['열차번호','열차종별','부산','비고']]
        if any(x is None for x in [id_row, kind_row, busan_row, note_row]):
            raise ValueError('일반열차 양식의 필수 행을 찾지 못했습니다.')
        event = '도착' if '하행' in labels[start] else '출발'
        for col in range(1, len(raw.columns)):
            tid, time = number(raw.iloc[id_row, col]), raw.iloc[busan_row, col]
            if not tid or not valid_time(time):
                continue
            days = offset(raw.iloc[id_row + 1:busan_row + 1, col].tolist())
            # 제공된 일반열차 양식은 비고 미기재가 별도 요일 제한 없음인 것으로 해석.
            note = weekday(raw.iloc[note_row, col], blank_is_daily=True)
            records.append(record(tid, raw.iloc[kind_row, col], event, time, note, days))
    return finish(records)
