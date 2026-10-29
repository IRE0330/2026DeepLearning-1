"""Sequential service consumer; runs outside the Streamlit process, spawn-safe."""
import json, sys, time, traceback
from core import db, DATA, ROOMS, TERMINAL, demo_profile
from analysis_runtime import runtime_info, validate_selection, start_room

def run(rid):
    with db() as c:
        request=json.loads(c.execute('SELECT request FROM runs WHERE id=?',(rid,)).fetchone()[0])
    try:
        runtime_info()
        validate_selection(request)
        from cctv import AnalysisService
        profile_path=DATA/rid/'cctv_profile.json'
        profile_path.parent.mkdir(parents=True,exist_ok=True)
        profile_path.write_text(json.dumps(demo_profile(request),ensure_ascii=False),encoding='utf-8')
        with AnalysisService() as service:
            for room in ROOMS:
                with db() as c:
                    if c.execute('SELECT stop FROM runs WHERE id=?',(rid,)).fetchone()[0]:
                        c.execute("UPDATE runs SET status='stopped' WHERE id=?",(rid,));return
                job=start_room(service,request,room,owner=rid,video_path=request['videos'][room],
                    # Service adds job_<id>/analysis/<run>/shared/<CSV>; keep below MAX_PATH.
                    output_dir=str(DATA.parent.parent/'analysis_runs'/rid),profile=str(profile_path),
                    end=request['end'] or None,save_video=request['save_video'])
                cursor=0;stop_sent=False
                while True:
                    batch=job.read_records(cursor,limit=1000)
                    status=job.status()
                    with db() as c:
                        for rec in batch.records:
                            c.execute('INSERT OR IGNORE INTO records VALUES(?,?,?,?,?)',
                                (rid,room,rec['record_id'],float(rec['interval_end_s']),json.dumps(rec,ensure_ascii=False)))
                        c.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)',(rid,room,status['status'],json.dumps(status,ensure_ascii=False)))
                        c.execute("UPDATE runs SET status='running',heartbeat=? WHERE id=?",(time.time(),rid))
                        stop=bool(c.execute('SELECT stop FROM runs WHERE id=?',(rid,)).fetchone()[0])
                    cursor=batch.next_cursor
                    if stop and not stop_sent:job.stop(wait=False);stop_sent=True
                    if batch.incomplete_tail and batch.done:raise RuntimeError('분석 기록 끝부분이 불완전합니다. 원본 CSV와 로그를 확인하세요.')
                    if batch.done:
                        if status.get('worker_alive'):
                            time.sleep(.1);continue
                        if status['status']!='completed':
                            with db() as c:c.execute('UPDATE runs SET status=?,error=? WHERE id=?',
                                ('stopped' if stop else 'failed',status.get('error') or status['status'],rid))
                            return
                        break
                    time.sleep(.25)
            with db() as c:c.execute("UPDATE runs SET status='completed',heartbeat=? WHERE id=?",(time.time(),rid))
    except BaseException as e:
        traceback.print_exc()
        with db() as c:c.execute("UPDATE runs SET status='failed',error=?,heartbeat=? WHERE id=?",(f'{type(e).__name__}: {e}',time.time(),rid))
        return 1
    return 0

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(run(sys.argv[1]))
