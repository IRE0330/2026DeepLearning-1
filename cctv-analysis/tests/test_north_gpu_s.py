import unittest
from unittest.mock import patch
from cctv.waiting_audit import confirmed_external
from cctv.gpu_profile import selection, start_north_gpu_s
from unittest.mock import Mock

class PolicyRegression(unittest.TestCase):
    def test_helper_delegates_only_explicit_north_gpu_options(self):
        service = Mock()
        selected = dict(restroom_id='north', device='cuda:0', model_path='checked-s.pt')
        with patch('cctv.gpu_profile.selection', return_value=selected) as select:
            job = start_north_gpu_s(service, owner='test', video_path='north.mp4',
                                    model_path='s.pt', output_dir='result',
                                    profile='demo', end=3.25, save_video=True)
        select.assert_called_once_with(model_path='s.pt')
        service.start.assert_called_once_with(owner='test', video_path='north.mp4',
            output_dir='result', profile='demo', end=3.25, save_video=True, **selected)
        self.assertIs(job, service.start.return_value)

    def check(self,candidates,confirmed,grace,total,csv):
        return confirmed_external(dict(waiting_candidate_observed=candidates,waiting_confirmed_observed=confirmed,
            waiting_observed=confirmed,waiting_grace=grace,waiting_total=total),{'외부대기인원_추정':str(csv)})
    def test_candidates_do_not_count(self):
        self.assertEqual(self.check(7,0,0,0,0),0)
        self.assertEqual(self.check(7,2,1,3,3),3)
    def test_candidate_inclusive_csv_rejected(self):
        with self.assertRaises(AssertionError):self.check(7,0,0,7,7)
    def test_wrong_confirmed_total_rejected(self):
        with self.assertRaises(AssertionError):self.check(7,2,1,2,2)
    def test_wrong_csv_rejected(self):
        with self.assertRaises(AssertionError):self.check(0,2,1,3,4)
    def test_s_is_not_selected_for_other_rooms_or_devices(self):
        for room,device in [('south','cuda:0'),('east','cuda:0'),('north','cpu'),('north','mps'),('north','auto')]:
            with self.subTest(room=room,device=device),self.assertRaises(ValueError):
                selection(restroom_id=room,device=device,model_path='does-not-exist.pt')
    def test_no_cuda_does_not_fall_back(self):
        with patch('torch.cuda.is_available',return_value=False),self.assertRaises(RuntimeError):
            selection(model_path='does-not-exist.pt')
    def test_missing_weights_is_clear(self):
        with patch('torch.cuda.is_available',return_value=True),self.assertRaises(FileNotFoundError):
            selection(model_path='does-not-exist.pt')
    def test_wrong_weights_cannot_run(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            model=Path(folder)/'yolo11s.pt';model.write_bytes(b'not the validated weights')
            with patch('torch.cuda.is_available',return_value=True),self.assertRaises(ValueError):
                selection(model_path=model)

if __name__=='__main__':unittest.main()
