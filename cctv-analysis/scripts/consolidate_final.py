"""Copy verified runs into final; archive unique evidence before deleting duplicates.

No inference, replay, numeric corrections, or tracker changes are performed.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cctv-analysis/src'))
from cctv.usage import USAGE_FIELDS
from cctv.media import verify_output


def fs(path):
    """Use Windows extended paths for deeply nested historical evidence."""
    return Path('\\\\?\\' + str(path.resolve())) if os.name == 'nt' else path


def sha(path):
    with fs(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def safe(path, parent):
    path, parent = path.resolve(), parent.resolve()
    if path == parent or not path.is_relative_to(parent):
        raise ValueError('Unsafe filesystem target')
    return path


def main():
    outputs = ROOT / 'outputs'
    final = outputs / 'final'
    if (final / 'manifest.json').is_file():
        previous = json.loads((final / 'manifest.json').read_text(encoding='utf-8'))
        if previous.get('method') == 'verified_copy_only_no_reanalysis_or_numeric_changes':
            raise ValueError('Final is already consolidated; refusing to archive it recursively.')
    stage = outputs / '_final031_stage'
    stage.mkdir(exist_ok=False)
    history = stage / 'evidence/history'
    history.mkdir(parents=True)
    names = ['confirmed_waiting_20261018_v020', 'confirmed_waiting_20261018_v020_r2',
             'confirmed_waiting_20261018_v030', 'east_extinguisher_20261018_v031']
    sources = [(final, history / 'original_final')] + [(outputs / n, history / n) for n in names]
    copied, skipped, mappings = [], [], []
    skip_dirs = {'installed', 'installed_final', '.cache', '__pycache__'}
    def copy_file(source, target):
        fs(target.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(fs(source), fs(target))
        digest = sha(source)
        assert digest == sha(target), source
        copied.append({'source': str(source), 'destination': str(final / target.relative_to(stage)),
                       'sha256_before_path_relocation': digest, 'bytes': fs(source).stat().st_size})
    for source, target in sources:
        for folder, dirs, files in os.walk(source):
            here = Path(folder)
            for name in list(dirs):
                if name in skip_dirs:
                    dirs.remove(name)
                    skipped.append({'path': str(here / name), 'reason': 'installed duplicate or runtime cache; not inspected/deleted'})
            for name in files:
                copy_file(here / name, target / (here / name).relative_to(source))
        mappings.append((str(source), str(final / target.relative_to(stage))))
    rooms = {}
    for room, name, expected_frames, fps in [('north', names[2], 2524, 24), ('south', names[2], 2827, 30), ('east', names[3], 2700, 30)]:
        base = outputs / name
        source = base / room / 'analysis'
        target = stage / room
        for p in source.iterdir():
            if p.is_file() and p.name != 'usage_summary.csv':
                copy_file(p, target / p.name)
        video = base / 'videos' / room / 'annotated.mp4'
        copy_file(video, target / 'annotated.mp4')
        csv_source, = (base / room / 'shared/shared').glob(f'{room}_*.csv')
        assert sha(csv_source) == sha(source / 'usage_summary.csv')
        copy_file(csv_source, target / 'shared' / csv_source.name)
        for p in (base / room / 'shared').iterdir():
            if p.is_file():
                copy_file(p, target / p.name)
        for p in (base / 'videos' / room).iterdir():
            if p.is_file() and p.name != 'annotated.mp4':
                copy_file(p, target / p.name)
        config = json.loads((target / 'config_used.json').read_text(encoding='utf-8'))
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        assert config['rules']['waiting_confirm_s'] == 3.5
        assert config['rules']['occlusion_grace_s'] == 1.5
        assert config['record_interval_s'] == 1 and config['csv_split_interval_s'] == 3600
        assert config['prediction_mode'] == 'disabled'
        assert config['rules'] == json.loads((ROOT / f'configs/{room}.json').read_text(encoding='utf-8'))['rules']
        for key in ('excluded_zones', 'boundary', 'waiting_zone', 'transit_zone', 'entry_direction'):
            assert config[key] == json.loads((ROOT / f'configs/{room}.json').read_text(encoding='utf-8'))[key]
        state = json.loads((target / 'final_state.json').read_text(encoding='utf-8'))
        assert state == summary['final_state']
        details = [json.loads(line) for line in (target / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
        csv_target = target / 'shared' / csv_source.name
        with csv_target.open(encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == USAGE_FIELDS
            rows = list(reader)
        assert len(rows) == len(details) == {'north': 105, 'south': 94, 'east': 90}[room]
        assert sha(csv_target) == sha(ROOT / 'cctv-analysis/examples/data' / csv_source.name)
        for row, detail in zip(rows, details):
            s = detail['state']
            assert s['waiting_total'] == s['waiting_confirmed_observed'] + s['waiting_grace']
            assert int(row['외부대기인원_추정']) == s['waiting_total']
        info = verify_output(target / 'annotated.mp4', *config['reference_size'], fps, expected_frames)
        assert summary['processed_frames'] == expected_frames
        assert summary['actual_start_s'] == 0
        assert sha(target / 'events.csv') == sha(source / 'events.csv')
        rooms[room] = {'source_run': str(source), 'frames': expected_frames, 'csv_rows': len(rows),
            'video': str(final / room / 'annotated.mp4'), 'csv': str(final / room / 'shared' / csv_source.name),
            'video_sha256': sha(video), 'csv_sha256': sha(csv_source), 'events_sha256': sha(source / 'events.csv'),
            'video_all_frames_decoded': info['all_frames_decoded'], 'entries': state['entries'], 'exits': state['exits'],
            'final_inside': state['inside_estimate'], 'waiting_confirm_s': 3.5, 'occlusion_grace_s': 1.5}
        mappings += [(str(source), str(final / room)),
                     (str(base / room / 'shared/shared'), str(final / room / 'shared')),
                     (str(source / 'usage_summary.csv'), str(final / room / 'shared' / csv_source.name)),
                     (str(base / room / 'shared'), str(final / room)),
                     (str(base / 'videos' / room), str(final / room))]
        # Common check files/previews remain discoverable outside raw history.
        evidence = stage / 'evidence' / name
        for p in base.iterdir():
            if p.is_file():
                copy_file(p, evidence / p.name)
        if (base / 'previews').is_dir():
            for p in (base / 'previews').rglob('*'):
                if p.is_file():
                    copy_file(p, evidence / 'previews' / p.relative_to(base / 'previews'))
    mappings = sorted(set(mappings), key=lambda p: len(p[0]), reverse=True)
    def relocate(value):
        if isinstance(value, dict): return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list): return [relocate(v) for v in value]
        if isinstance(value, str):
            for before, after in mappings:
                if value == before or value.startswith(before + os.sep): return after + value[len(before):]
        return value
    # Preserve archived source bytes unchanged; working copies receive new paths.
    relocated = []
    working_files = []
    for folder, dirs, files in os.walk(stage):
        if Path(folder) == stage / 'evidence':
            dirs[:] = [d for d in dirs if d != 'history']
        working_files.extend(Path(folder) / name for name in files)
    for p in working_files:
        if not p.is_file() or p.is_relative_to(history): continue
        if p.suffix in ('.json', '.jsonl'):
            original = p.read_text(encoding='utf-8-sig')
            if p.suffix == '.json':
                revised = json.dumps(relocate(json.loads(original)), ensure_ascii=False, indent=2) + '\n'
            else:
                revised = ''.join(json.dumps(relocate(json.loads(line)), ensure_ascii=False) + '\n' for line in original.splitlines())
            if revised != original:
                p.write_text(revised, encoding='utf-8')
                relocated.append(str(final / p.relative_to(stage)))
    for room in rooms:
        folder = stage / room
        records = [json.loads(s) for s in (folder / 'record_index.jsonl').read_text(encoding='utf-8').splitlines()]
        with next((folder / 'shared').glob('*.csv')).open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        for record, row in zip(records, rows):
            assert Path(record['csv_ref']['path']) == Path(rooms[room]['csv'])
            assert row == {k: '' if v is None else str(v) for k, v in record['csv_row'].items()}
        assert len(records) == len(rows)
    (stage / 'path_relocation.json').write_text(json.dumps({'mappings': mappings,
        'scope': 'working metadata rewritten; raw history immutable with original paths resolved by this map',
        'relocated_files': relocated}, ensure_ascii=False, indent=2), encoding='utf-8')
    (stage / 'manifest.json').write_text(json.dumps({'version': '0.3.1', 'rooms': rooms,
        'method': 'verified_copy_only_no_reanalysis_or_numeric_changes', 'copied_file_count': len(copied)}, ensure_ascii=False, indent=2), encoding='utf-8')
    (stage / 'copy_verification.json').write_text(json.dumps(copied, ensure_ascii=False, indent=2), encoding='utf-8')
    (stage / 'cleanup_plan.json').write_text(json.dumps({'sources': [str(s) for s, _ in sources],
        'preserved_raw_history': str(final / 'evidence/history'), 'not_inspected_or_deleted': skipped}, ensure_ascii=False, indent=2), encoding='utf-8')
    hold = safe(outputs / 'final_pre031_verified_hold', outputs)
    assert not hold.exists()
    safe(final, outputs); safe(stage, outputs)
    shutil.move(str(final), str(hold))
    shutil.move(str(stage), str(final))
    # Deletion is a separate, explicit phase after reviewing this verification.
    print(json.dumps({'version': '0.3.1', 'rooms': rooms, 'verified_copies': len(copied),
                      'previous_final_hold': str(hold)}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
