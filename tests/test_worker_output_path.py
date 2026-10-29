"""The dashboard output root must leave room for the service's nested filenames."""
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'busan_restroom_dashboard'))
import worker


class WorkerOutputPath(unittest.TestCase):
    def test_service_uses_short_root_and_preserves_request(self):
        rid='a'*32
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            database=root/'dashboard.sqlite'
            request={'videos':{r:f'{r}.mp4' for r in worker.ROOMS},
                     'configs':{r:'' for r in worker.ROOMS},'model':'model.pt',
                     'device':'cpu','end':5.,'save_video':False}
            @contextmanager
            def db():
                connection=sqlite3.connect(database)
                try:
                    with connection:
                        yield connection
                finally:
                    connection.close()
            with db() as c:
                c.executescript('CREATE TABLE runs(id TEXT,status TEXT,request TEXT,stop INTEGER,heartbeat REAL,error TEXT);'
                                'CREATE TABLE jobs(run TEXT,room TEXT,status TEXT,payload TEXT);'
                                'CREATE TABLE records(run TEXT,room TEXT,rid TEXT,t REAL,payload TEXT);')
                c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(rid,'preparing',json.dumps(request),0,0,''))
            calls=[]
            class Service:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def start(self,**kw):
                    calls.append(kw)
                    return SimpleNamespace(read_records=lambda *a,**k:SimpleNamespace(records=[],next_cursor=0,incomplete_tail=False,done=True),
                                           status=lambda:{'status':'completed','worker_alive':False})
            with patch.object(worker,'DATA',root/'busan_restroom_dashboard/data'),patch.object(worker,'db',db),patch('cctv.AnalysisService',Service):
                self.assertEqual(worker.run(rid),0)
            self.assertEqual(len(calls),3)
            for call in calls:
                self.assertEqual(Path(call['output_dir']),root/'analysis_runs'/rid)
                self.assertEqual(call['end'],5.)
                self.assertEqual(call['video_path'],request['videos'][call['restroom_id']])
            with db() as c:
                status,stored=c.execute('SELECT status,request FROM runs').fetchone()
                self.assertEqual(status,'completed')
                self.assertEqual(json.loads(stored),request)

    def test_this_workspace_shared_csv_path_fits_legacy_windows_limit(self):
        for room in worker.ROOMS:
            path=PROJECT/'analysis_runs'/('a'*32)/('job_'+'b'*32)/'analysis'/f'{room}_20261025_001828_ecaa9535'/'shared'/f'{room}_2026-10-14_1400.csv'
            self.assertLess(len(str(path)),260)


if __name__=='__main__':unittest.main()
