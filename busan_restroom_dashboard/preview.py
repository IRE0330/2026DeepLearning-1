"""Prepare a compatible browser preview; inference always uses the original."""
from pathlib import Path
import hashlib
import subprocess
import sys


def browser_preview(source, cache_dir):
    import av
    source = Path(source).expanduser().resolve()
    stat = source.stat()
    fingerprint = f'{source}:{stat.st_size}:{stat.st_mtime_ns}:h264-preview-v1'
    output = Path(cache_dir) / (hashlib.sha256(fingerprint.encode()).hexdigest()[:24] + '.mp4')
    if output.is_file() and output.stat().st_size > 0:
        return output
    with av.open(str(source)) as container:
        if not container.streams.video:
            raise ValueError('영상 트랙이 없습니다.')
        codec = container.streams.video[0].codec_context
        pixel_format = codec.format.name if codec.format else ''
        compatible = source.suffix.lower() == '.mp4' and codec.name == 'h264' and pixel_format == 'yuv420p'
    if compatible:
        return source
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name('transcode.py')), str(source), str(output)],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError('브라우저용 MP4 변환에 실패했습니다. ' + result.stderr[-500:])
    return output
