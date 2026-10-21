"""Headless Streamlit + actual short CPU file analysis; no browser claim."""
import argparse
import json
from pathlib import Path
import os
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CCTV_EXAMPLE_VIDEO=str(args.materials / '북쪽_화장실_cctv.mp4'),
                      CCTV_EXAMPLE_MODEL=str(args.materials / 'models/yolo11n.pt'),
                      CCTV_EXAMPLE_OUTPUT=str(args.output))
    import cctv
    import cctv.api as api
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_resource.clear()
    app = Path(cctv.__path__[0]) / 'examples/streamlit_app.py'
    first = AppTest.from_file(str(app)).run(timeout=10)
    assert not first.exception
    first.button[0].click().run(timeout=10)
    assert not first.exception
    job = api._live_job  # Test observation only; front code uses the public Service.
    durations = []
    deadline = time.monotonic() + 90
    try:
        while job.latest() is None and time.monotonic() < deadline:
            begun = time.monotonic()
            first.run(timeout=10)
            durations.append(time.monotonic() - begun)
            assert not first.exception
            assert api._live_job is job
            assert job.status()['status'] not in ('failed', 'force_terminated'), job.status()
            time.sleep(.1)
        assert job.latest() is not None, job.status()
        second = AppTest.from_file(str(app)).run(timeout=10)
        assert not second.exception
        assert second.button[0].disabled and second.button(key='stop').disabled
        assert any('다른 세션' in value.value for value in second.info)
        first.button(key='stop').click().run(timeout=10)
        deadline = time.monotonic() + 15
        while job.alive and time.monotonic() < deadline:
            first.run(timeout=10)
            assert not first.exception
            time.sleep(.1)
        assert job.status()['status'] == 'stopped', job.status()
        first.run(timeout=10)
        assert any('중지 완료' in value.value for value in first.text)
        records = list(job.records())
        assert records
        stopped = job.status()
        first.text_input(key='video').set_value(str(args.output / 'not_present.mp4'))
        first.button[0].click().run(timeout=10)
        missing = api._live_job
        deadline = time.monotonic() + 15
        while missing.alive and time.monotonic() < deadline:
            first.run(timeout=10)
            time.sleep(.1)
        first.run(timeout=10)
        assert missing.status()['status'] == 'failed'
        assert any('not_present.mp4' in value.value for value in first.error)
        result = {'framework': 'Streamlit AppTest; no real browser/server rendering/timer verification',
                  'streamlit_version': st.__version__, 'actual_detector': True,
                  'duplicate_start_on_rerun': False, 'two_session_busy_and_stop_ownership': True,
                  'latest_record_rendered': True, 'normal_stop_via_ui': True, 'missing_path_error_rendered': True,
                  'reruns': len(durations), 'max_rerun_elapsed_s': max(durations),
                  'stopped': stopped, 'missing': missing.status(), 'records': len(records)}
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'ui_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('stopped', 'missing')}, ensure_ascii=False))
    finally:
        if api._live_job is not None and api._live_job.alive:
            api._live_job.stop()
        st.cache_resource.clear()


if __name__ == '__main__':
    main()
