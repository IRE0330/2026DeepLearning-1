import os
import tempfile
import time
import unittest
from unittest.mock import patch
from cctv.api import AnalysisService


def stuck_worker(*_):
    time.sleep(30)


def crashed_worker(*_):
    os._exit(7)


class Termination(unittest.TestCase):
    def test_stop_timeout_is_distinct_from_completed(self):
        with tempfile.TemporaryDirectory() as folder, patch('cctv.api._worker', stuck_worker), AnalysisService() as service:
            job = service.start(owner='one', restroom_id='north', output_dir=folder)
            job.stop(timeout=.01)
            self.assertFalse(job.alive)
            self.assertEqual(job.status()['status'], 'force_terminated')

    def test_abrupt_worker_exit_is_failure_not_empty_success(self):
        with tempfile.TemporaryDirectory() as folder, patch('cctv.api._worker', crashed_worker), AnalysisService() as service:
            job = service.start(owner='one', restroom_id='north', output_dir=folder)
            self.assertEqual(list(job.records()), [])
            self.assertEqual(job.status()['status'], 'failed')
            self.assertIn('exitcode=7', job.status()['error'])


if __name__ == '__main__':
    unittest.main()
