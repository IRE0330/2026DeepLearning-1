"""Audit exported batch rows against detailed states/events, not against human truth."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cctv.usage import USAGE_FIELDS


def read_csv(path):
    assert path.read_bytes().startswith(b'\xef\xbb\xbf'), str(path)
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def verify_batch(path):
    path = Path(path)
    batch = json.loads((path / 'batch_summary.json').read_text(encoding='utf-8'))
    audits = []
    for result in batch['results']:
        if result['status'] != 'completed':
            audits.append({'registration': result['registration'], 'status': result['status'],
                           'error': result['error']})
            continue
        run = Path(result['run_dir'])
        summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
        config = json.loads((run / 'config_used.json').read_text(encoding='utf-8'))
        assert summary['output_video']['all_frames_decoded']
        fields, rows = read_csv(run / 'usage_summary.csv')
        assert fields == USAGE_FIELDS and len(fields) == 13
        _, events = read_csv(run / 'events.csv')
        details = [json.loads(line) for line in (run / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(rows) == len(details) == summary['regular_csv_rows']
        interval_s = summary['periodic_interval_s']
        for i, (row, detail) in enumerate(zip(rows, details)):
            begin, end = detail['interval_start_s'], detail['interval_end_s']
            assert abs(end - begin - interval_s) < 1e-9
            assert detail['source_time_s'] <= end + 1e-9
            selected = [e for e in events if (float(e['video_time_s']) >= begin - 1e-9 if i == 0
                        else float(e['video_time_s']) > begin + 1e-9) and float(e['video_time_s']) <= end + 1e-9]
            for direction, key in [('entry', '구간_입장인원'), ('exit', '구간_퇴장인원')]:
                assert int(row[key]) == sum(e['direction'] == direction for e in selected)
            state = detail['state']
            if config['initial_inside'] is not None:
                assert int(row['내부잔류인원_추정']) == config['initial_inside'] + state['entries'] - state['exits']
            assert row['현재대기인원_추정'] == row['전체대기인원_추정']
            assert int(row['외부대기인원_추정']) == state['waiting_total']
            for key, state_key in [('추정내부대기인원', 'internal_waiting_estimate'),
                                   ('전체대기인원_추정', 'total_queue_estimate'),
                                   ('현재이용가능칸수_추정', 'available_stalls_estimate')]:
                expected = state.get(state_key)
                assert row[key] == (str(expected) if expected is not None else '')
            base = config.get('capture_start_time')
            if base:
                assert datetime.fromisoformat(row['촬영시작시각']) == datetime.fromisoformat(base) + timedelta(seconds=begin)
                assert datetime.fromisoformat(row['촬영종료시각']) == datetime.fromisoformat(base) + timedelta(seconds=end)
            else:
                assert row['촬영시작시각'] == row['촬영종료시각'] == ''
        remainder = summary['remainder']
        assert 0 <= remainder['duration_s'] < interval_s
        for direction, key in [('entry', 'entries'), ('exit', 'exits')]:
            regular = sum(int(r['구간_입장인원' if key == 'entries' else '구간_퇴장인원']) for r in rows)
            assert regular + remainder[key] == summary['final_state'][key]
        audits.append({'run_dir': str(run), 'status': 'completed', 'rows': len(rows),
                       'frames': summary['processed_frames'], 'elapsed_s': summary['elapsed_s'],
                       'device': summary['model']['device'], 'final_state': summary['final_state'],
                       'remainder_s': remainder['duration_s'], 'all_output_frames_decoded': True})
    for file in batch['shared_csv']:
        fields, rows = read_csv(Path(file['path']))
        assert fields == USAGE_FIELDS and len(rows) == file['rows']
        assert len({r['화장실ID'] for r in rows}) == 1
        assert rows == sorted(rows, key=lambda r: (datetime.fromisoformat(r['촬영종료시각']).timestamp()
                                                   if r['촬영종료시각'] else float('-inf'), r['화장실_영상ID']))
    return {'batch': str(path), 'status': batch['status'], 'items': audits, 'shared_csv': batch['shared_csv']}


if __name__ == '__main__':
    results = [verify_batch(p) for p in sys.argv[1:]]
    original = json.loads((ROOT / 'docs/batch_preservation_before.json').read_text(encoding='utf-8'))
    preserved = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest for p, digest in original.items()}
    assert all(preserved.values()), preserved
    reference = ROOT / 'outputs/north_20261014_153548_3ce00c43/north_demo_2026-10-14_10s_v3.csv'
    with reference.open(encoding='utf-8-sig', newline='') as f:
        assert next(csv.reader(f)) == USAGE_FIELDS
    report = {'kind': 'export_consistency_not_accuracy', 'tests': results, 'existing_configs_preserved': preserved,
              'reference_header_exact_match': True, 'accuracy_evaluation': 'not_performed_no_manual_truth'}
    (ROOT / 'docs/batch_export_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Export consistency PASS; source configs/previews preserved; reference 13 headers match.')
