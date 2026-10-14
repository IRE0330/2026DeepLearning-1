"""Record read-only preservation and artifact checks for this continuation."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cctv.config import load, validate
from cctv.media import write_json

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

before = json.loads(Path('docs/preserved_inputs_before.json').read_text(encoding='utf-8'))
preservation = {p: Path(p).is_file() and digest(Path(p)) == value for p, value in before.items()}
configs = {}
for rid in ('north', 'south', 'east'):
    c = load(f'configs/{rid}.json')
    validate(c, require_zones=False)
    try:
        validate(c)
        reason = None
    except ValueError as exc:
        reason = str(exc)
    configs[rid] = {'video': c['video'], 'video_exists': Path(c['video']).is_file(),
                    'configured': c['configured'], 'analysis_validation_error': reason,
                    'truth_rows': {p.name: len(list(csv.DictReader(p.open(encoding='utf-8-sig'))))
                                   for p in Path('ground_truth', rid).glob('*.csv')}}
baselines, sequences = [], []
for p in sorted(Path('outputs').glob('*/summary.json')):
    report = json.loads(p.read_text(encoding='utf-8'))
    record = {'run_dir': str(p.parent), 'status': report['status'], 'mode': report['mode'],
              'processed_frames': report['processed_frames'], 'elapsed_s': report.get('elapsed_s'),
              'device': report.get('model', {}).get('device'),
              'all_output_frames_decoded': report.get('output_video', {}).get('all_frames_decoded')}
    if report['mode'] == 'baseline':
        record['artifacts_exist'] = {name: (p.parent / name).is_file() for name in
            ('annotated.mp4', 'events.csv', 'timeseries.csv', 'diagnostics.jsonl', 'final_state.json', 'config_used.json')}
        record['count_csv_rows'] = {name: len(list(csv.DictReader((p.parent / name).open(encoding='utf-8-sig'))))
                                    for name in ('events.csv', 'timeseries.csv')}
        baselines.append(record)
    elif report['mode'] == 'rgb_sequence_tracking':
        record.update(first_frame_number=report.get('first_frame_number'), last_frame_number=report.get('last_frame_number'))
        sequences.append(record)
with zipfile.ZipFile('data/micc_crowd_counting.zip') as z:
    archive = {'central_directory_readable': True, 'entries': len(z.infolist()),
               'full_crc_test_performed': False, 'download_restarted': False}
write_json(Path('docs/continuation_checks.json'), {
    'date': '2026-10-14', 'preserved_inputs': preservation,
    'all_original_inputs_unchanged': all(preservation.values()),
    'config_and_truth_status': configs, 'existing_baseline_artifacts': baselines,
    'micc_sequence_artifacts': sequences, 'micc_archive': archive,
    'tests': {'command': 'python -X utf8 -m unittest discover -s tests -v', 'passed': 23,
              'basis': 'actual test process exit 0; synthetic rules and export, not video accuracy'}})
pending = Path('inspections/east_pending')
pending.mkdir(exist_ok=True)
actual_inspections = sorted(Path('inspections').glob('east_*/video_info.json'))
actual_inspections = [p for p in actual_inspections if p.parent != pending]
if actual_inspections:
    write_json(pending / 'video_info.json', {
        'restroom_id': 'east', 'status': 'resolved_see_actual_inspection',
        'path': load('configs/east.json')['video'], 'actual_report': str(actual_inspections[-1]),
        'reason': '처음에는 경로 자리표시자여서 대기했으나, 사용자 제공 실제 파일을 검사했습니다. 실제 측정값은 actual_report를 보세요.'})
else:
    write_json(pending / 'video_info.json', {
        'restroom_id': 'east', 'status': 'awaiting_actual_video_path',
        'path': load('configs/east.json')['video'], 'video_inspection_performed': False,
        'reason': '실제 영상 검사 보고서가 없습니다.'})
print('Preserved original inputs:', all(preservation.values()), len(preservation))
print('Baseline artifacts:', len(baselines), 'MICC sequence runs:', len(sequences))
