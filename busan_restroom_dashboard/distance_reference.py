"""Portable annotations selected by exact original-video bytes, not PC paths."""
import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

REFERENCE_PATH = Path(__file__).resolve().parents[1] / 'configs/distance_reference.json'
ROOMS = ('north', 'east', 'south')


@lru_cache(maxsize=32)
def _file_digest(path, stamp):
    h = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    if _stamp(Path(path)) != stamp:
        raise OSError('Video changed while computing its fingerprint')
    return h.hexdigest()


def _stamp(path):
    s = path.stat()
    return s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino


def video_fingerprint(source):
    """Full-file SHA-256; cache repeated reads until local file metadata changes."""
    if not source:
        return ''
    try:
        path = Path(source).expanduser().resolve()
        return _file_digest(str(path), _stamp(path)) if path.is_file() else ''
    except (OSError, ValueError):
        return ''


def load_reference():
    try:
        data = json.loads(REFERENCE_PATH.read_text(encoding='utf-8'))
        if (isinstance(data, dict) and data.get('schema_version') == 1
                and data.get('fingerprint_algorithm') == 'sha256'
                and data.get('coordinate_system') == 'normalized_xy'
                and isinstance(data.get('rooms'), dict)):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _entry(reference, room):
    from distance_demo import validate_lines
    from distance_policy import active_meters
    entry = reference.get('rooms', {}).get(room)
    if (not isinstance(entry, dict) or validate_lines(entry,active_meters(room))
            or not isinstance(entry.get('video_sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', entry['video_sha256'])
            or not isinstance(entry.get('legacy_source_keys', []), list)
            or any(not isinstance(k, str) or not re.fullmatch('[0-9a-f]{64}', k)
                   for k in entry.get('legacy_source_keys', []))):
        return None
    return entry


def _source(cfg, room):
    # app.py supplies the exact same effective source used for video playback.
    return cfg.get('distance_current_videos', cfg.get('videos', {})).get(room, '')


def _shared_for(cfg, room, reference):
    from distance_demo import video_key
    entry = _entry(reference, room)
    if not entry:
        return None
    source = _source(cfg, room)
    digest = video_fingerprint(source)
    if not digest or digest != entry['video_sha256']:
        return None
    frozen_digest = cfg.get('distance_video_fingerprints', {}).get(room)
    frozen_key = cfg.get('distance_video_keys', {}).get(room)
    if frozen_digest is not None:
        if frozen_digest != digest:
            return None
    elif frozen_key is not None:
        # Only explicitly verified legacy bindings may bridge an old run's key.
        aliases = entry.get('legacy_source_keys', [])
        if frozen_key != video_key(source) and frozen_key not in aliases:
            return None
    setting = copy.deepcopy(entry)
    setting['source_key'] = 'sha256:' + digest
    return setting, setting['source_key']


def settings_for(cfg, room):
    """Prefer a verified shared annotation; retain safe local legacy settings."""
    from distance_demo import video_key
    local = cfg.get('distance_demo', {}).get(room, {})
    source = _source(cfg, room)
    reference = load_reference()
    shared = _shared_for(cfg, room, reference)
    if shared is not None:
        return shared
    key = video_key(source)
    frozen_digest = cfg.get('distance_video_fingerprints', {}).get(room)
    if frozen_digest is not None and frozen_digest != video_fingerprint(source):
        return local, ''
    frozen = cfg.get('distance_video_keys', {}).get(room)
    if frozen is not None and frozen != key:
        key = ''
    entry = _entry(reference, room)
    if (entry and local.get('source_key') in entry.get('legacy_source_keys', [])
            and video_fingerprint(source) != entry['video_sha256']):
        key = ''
    return local, key


def shared_editor_hidden(cfg):
    """Hide only the editor, and only after every connected camera verifies."""
    reference = load_reference()
    return reference.get('hide_editor') is True and all(
        _shared_for(cfg, room, reference) is not None for room in ROOMS)


def build_reference(cfg):
    """Export validated local annotations without paths, credentials or run data."""
    from distance_demo import DISCLAIMER, validate_lines, video_key
    from distance_policy import active_meters
    rooms = {}
    for room in ROOMS:
        source = cfg.get('videos', {}).get(room, '')
        setting = cfg.get('distance_demo', {}).get(room, {})
        issue = validate_lines(setting,active_meters(room))
        legacy_key = video_key(source)
        if issue or not legacy_key or setting.get('source_key') != legacy_key:
            raise ValueError(f'{room}: annotations do not match the connected video: {issue or "source key"}')
        digest = video_fingerprint(source)
        if not digest:
            raise ValueError(f'{room}: cannot fingerprint video')
        frame = setting.get('frame_s', 0.)
        if not isinstance(frame, (int, float)) or not math.isfinite(frame) or frame < 0:
            raise ValueError(f'{room}: invalid reference frame')
        rooms[room] = {
            'video_sha256': digest, 'legacy_source_keys': [legacy_key],
            'origin': copy.deepcopy(setting['origin']),
            'lines': copy.deepcopy(setting['lines']), 'frame_s': frame, 'label': DISCLAIMER,
        }
        for key in ('overflow_boundary','overflow_seconds'):
            if key in setting:rooms[room][key]=copy.deepcopy(setting[key])
    return {'schema_version': 1, 'fingerprint_algorithm': 'sha256',
            'coordinate_system': 'normalized_xy', 'hide_editor': False, 'rooms': rooms}
