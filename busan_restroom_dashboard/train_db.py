"""Read scheduled Busan train events from the existing MySQL table."""
from datetime import date, datetime, timedelta
import pandas as pd

SELECT_COLUMNS='CAST(`날짜` AS CHAR) AS `날짜`, `열차번호`, `열차종류`, `운행구분`, CAST(`예정시각` AS CHAR) AS `예정시각`'

class TrainDatabaseError(Exception):pass

def connect(config):
    try:import mysql.connector
    except ImportError:raise TrainDatabaseError('MySQL 연결 패키지가 없습니다. python -m pip install mysql-connector-python 을 실행해주세요.') from None
    try:
        return mysql.connector.connect(host=config.get('host','127.0.0.1'),port=int(config.get('port',3306)),database=config.get('database','railway_system'),user=config.get('user','root'),password=config.get('password',''),charset='utf8mb4',use_unicode=True,connection_timeout=5,autocommit=True)
    except Exception as exc:raise friendly_error(exc) from None

def friendly_error(exc):
    code=getattr(exc,'errno',None)
    if code==1045:return TrainDatabaseError('MySQL 로그인이 거부됐습니다. 사용자와 비밀번호를 확인해주세요.')
    if code==1049:return TrainDatabaseError('railway_system 데이터베이스가 없습니다. 기존 DB 이름을 확인해주세요.')
    if code in (1146,1054):return TrainDatabaseError('열차_운행정보 테이블 또는 필요한 열이 없습니다. railway_system_v5에서 사용하는 DB인지 확인해주세요.')
    return TrainDatabaseError('MySQL 조회에 실패했습니다. 서버 실행 여부, 호스트·포트와 조회 권한을 확인해주세요.')

def query(config,sql,params=()):
    conn=connect(config);cur=None
    try:
        cur=conn.cursor(dictionary=True);cur.execute(sql,params);return cur.fetchall()
    except Exception as exc:raise friendly_error(exc) from None
    finally:
        try:
            if cur is not None:cur.close()
        finally:conn.close()

def available_dates(config):
    rows=query(config,'SELECT DISTINCT CAST(`날짜` AS CHAR) AS day FROM `열차_운행정보` ORDER BY day')
    return [date.fromisoformat(str(row['day'])) for row in rows if row['day']]

def load_schedule(config,day,include_next=False):
    first=date.fromisoformat(str(day));last=first+timedelta(days=int(include_next))
    rows=query(config,'SELECT '+SELECT_COLUMNS+' FROM `열차_운행정보` WHERE `날짜` BETWEEN %s AND %s ORDER BY `날짜`,`예정시각`,`열차번호`',(first.isoformat(),last.isoformat()))
    df=pd.DataFrame(rows,columns=['날짜','열차번호','열차종류','운행구분','예정시각'])
    df['예정일시']=pd.to_datetime(df['날짜'].astype(str)+' '+df['예정시각'].astype(str),errors='coerce')
    df=df.dropna(subset=['예정일시']).drop_duplicates(subset=['예정일시','열차번호','운행구분'])
    return df.sort_values(['예정일시','열차번호']).reset_index(drop=True)

def timeline_events(frame,capture_date):
    origin=datetime.combine(date.fromisoformat(str(capture_date)),datetime.min.time())+timedelta(hours=14)
    return [{'offset_s':(row['예정일시'].to_pydatetime()-origin).total_seconds(),'time':row['예정일시'].strftime('%H:%M:%S'),'day':row['예정일시'].strftime('%Y-%m-%d'),'number':str(row['열차번호']),'kind':str(row['열차종류'] or ''),'event':str(row['운행구분'])} for _,row in frame.iterrows() if str(row['운행구분']).strip() in ('도착','출발')]
