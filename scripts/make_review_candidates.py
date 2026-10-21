"""Create a review index from automatic logs, never human ground-truth labels."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cctv.media import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    sources = {
        'north': Path('outputs/final/north'),
        'south': Path('outputs/final/south'),
        'east': Path('outputs/final/east')}
    candidates, provenance = [], {}
    for room, folder in sources.items():
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        duration = summary['input_video']['duration_s'] if 'input_video' in summary else {'north': 105.166667, 'south': 94.233333, 'east': 90}[room]
        events = []
        with (folder / 'events.csv').open(encoding='utf-8-sig', newline='') as handle:
            events = list(csv.DictReader(handle))
        windows = []
        for event in events:
            start = max(0, min(float(event['video_time_s']), float(event['crossing_time_estimate_s'])) - 2)
            end = min(duration, float(event['video_time_s']) + 2)
            if windows and start <= windows[-1][1] + 1:
                windows[-1][1] = max(end, windows[-1][1])
            else:
                windows.append([start, end])
        for start, end in windows:
            candidates.append(dict(restroom_id=room, start_s=round(start, 3), end_s=round(end, 3),
                                   review_reason='자동 출입 후보 주변: 방향·경계 통과·되돌아감 확인',
                                   source=str(folder), is_ground_truth=False))
        with (folder / 'timeseries.csv').open(encoding='utf-8-sig', newline='') as handle:
            series = list(csv.DictReader(handle))
        if series:
            peak = max(series, key=lambda r: int(r['waiting_total']))
            center = float(peak['sample_time_s'])
            candidates.append(dict(restroom_id=room, start_s=round(max(0, center - 2), 3),
                                   end_s=round(min(duration, center + 5), 3),
                                   review_reason='자동 외부 대기 최대 구간: 새 대기자·확정 대기자·중복·통행 구분',
                                   source=str(folder), is_ground_truth=False))
        gap = None
        kinds = ('grace_count_suppressed_possible_duplicate', 'crossing_unconfirmed_after_gap', 'waiting_grace_expired')
        with (folder / 'diagnostics.jsonl').open(encoding='utf-8') as handle:
            for line in handle:
                record = json.loads(line)
                if record['kind'] in kinds and record['video_time_s'] >= 2:
                    gap = record
                    break
        if gap:
            center = gap['video_time_s']
            candidates.append(dict(restroom_id=room, start_s=round(max(0, center - 2), 3),
                                   end_s=round(min(duration, center + 3), 3),
                                   review_reason='자동 가림/유예/중복 억제 후보: 전후 동일 사람 여부 확인 (' + gap['kind'] + ')',
                                   source=str(folder), is_ground_truth=False))
        if room == 'north':
            candidates.append(dict(restroom_id=room, start_s=30, end_s=36,
                                   review_reason='이전 CPU/GPU 세부 상태 차이 구간: 대기·가림 확인; 이번 속도 제어 차이 아님',
                                   source=str(folder), is_ground_truth=False))
        if room == 'south':
            candidates.append(dict(restroom_id=room, start_s=88, end_s=round(duration, 3),
                                   review_reason='종료 직전 미확정 후보와 가림·출입 여부 확인',
                                   source=str(folder), is_ground_truth=False))
        provenance[room] = str(folder)
    with (output / 'manual_review_candidates.csv').open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, ['restroom_id', 'start_s', 'end_s', 'review_reason', 'source', 'is_ground_truth'])
        writer.writeheader()
        writer.writerows(sorted(candidates, key=lambda r: (r['restroom_id'], r['start_s'])))
    write_json(output / 'manual_review_sources.json', {'sources': provenance,
               'purpose': 'Automatic review index only; no truth labels or accuracy scores generated.',
               'ground_truth_templates_modified': False})
    print(output / 'manual_review_candidates.csv')


if __name__ == '__main__':
    main()
