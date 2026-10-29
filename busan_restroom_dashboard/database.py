"""부산역 날짜별 예정 운행을 기존 MySQL 테이블에 저장한다."""
from datetime import date, time
import pandas as pd

COLUMNS = ['날짜', '열차번호', '열차종류', '운행구분', '예정시각']
LOCK_NAME = 'railway_system.train_import_v5'

def prepare_rows(frame):
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError('필수 컬럼 누락: ' + ', '.join(sorted(missing)))
    rows, seen, duplicates = [], {}, 0
    for index, row in enumerate(frame[COLUMNS].itertuples(index=False, name=None), 1):
        if any(pd.isna(value) for value in row):
            raise ValueError(f'{index}번째 기록에 필수값이 비어 있습니다.')
        day, number, kind, event, clock = (str(value).strip() for value in row)
        day = date.fromisoformat(day).isoformat()
        parsed = time.fromisoformat(clock)
        if parsed.tzinfo is not None or parsed.microsecond:
            raise ValueError('예정시각은 초 단위 HH:MM:SS 형식이어야 합니다.')
        clock = parsed.strftime('%H:%M:%S')
        if not number or len(number) > 20 or not kind or len(kind) > 30 or event not in ('도착', '출발'):
            raise ValueError(f'{index}번째 기록의 열차번호·열차종류·운행구분을 확인하세요.')
        key = (day, number, event, clock)
        if key in seen:
            if seen[key] != kind:
                raise ValueError(f'같은 운행의 열차종류가 다릅니다: {key}')
            duplicates += 1
            continue
        seen[key] = kind
        rows.append((day, number, kind, event, clock))
    return rows, duplicates

def connect(config):
    import mysql.connector
    return mysql.connector.connect(**config, charset='utf8mb4', use_unicode=True,
                                   connection_timeout=10, autocommit=False)

def check_connection(config):
    connection = connect(config)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute('SELECT VERSION()')
            version = cursor.fetchone()[0]
            cursor.execute('SELECT `날짜`,`열차번호`,`열차종류`,`운행구분`,`예정시각` FROM `열차_운행정보` LIMIT 0')
            cursor.fetchall()
            return version
        finally:
            cursor.close()
    finally:
        connection.close()

def save_records(frame, config):
    rows, source_duplicates = prepare_rows(frame)
    if not rows:
        return {'inserted': 0, 'skipped': source_duplicates}
    connection = connect(config)
    cursor = None
    locked = False
    try:
        cursor = connection.cursor()
        # 이 앱의 동시 저장 요청을 직렬화한다. 기존 DB 스키마는 변경하지 않는다.
        cursor.execute('SELECT GET_LOCK(%s, 10)', (LOCK_NAME,))
        locked = cursor.fetchone()[0] == 1
        if not locked:
            raise ValueError('다른 저장 작업이 진행 중입니다. 잠시 후 다시 눌러주세요.')
        cursor.execute("SELECT CAST(`날짜` AS CHAR), `열차번호`, `열차종류`, `운행구분`, CAST(`예정시각` AS CHAR) FROM `열차_운행정보` WHERE `날짜` BETWEEN %s AND %s",
                       (min(row[0] for row in rows), max(row[0] for row in rows)))
        existing = {}
        for day, number, kind, event, clock in cursor.fetchall():
            existing.setdefault((day, str(number), event, clock), set()).add(kind)
        pending, skipped = [], source_duplicates
        for row in rows:
            day, number, kind, event, clock = row
            key = (day, number, event, clock)
            if key in existing:
                if existing[key] != {kind}:
                    raise ValueError(f'DB의 기존 열차종류와 다릅니다: {day} {number} {event} {clock}. 기존 기록을 확인하세요.')
                skipped += 1
            else:
                pending.append(row)
        sql = 'INSERT INTO `열차_운행정보` (`날짜`,`열차번호`,`열차종류`,`운행구분`,`예정시각`) VALUES (%s,%s,%s,%s,%s)'
        for start in range(0, len(pending), 500):
            cursor.executemany(sql, pending[start:start + 500])
        connection.commit()
        return {'inserted': len(pending), 'skipped': skipped}
    except Exception:
        connection.rollback()
        raise
    finally:
        # 연결 종료 시에도 MySQL이 명명 잠금을 해제한다.
        if cursor is not None:
            try:
                if locked:
                    cursor.execute('SELECT RELEASE_LOCK(%s)', (LOCK_NAME,))
                    cursor.fetchone()
            finally:
                cursor.close()
                connection.close()
        else:
            connection.close()
