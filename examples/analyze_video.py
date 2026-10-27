"""Actual file analysis via public API; guarded for Windows spawn."""
import argparse
import json
from cctv import AnalysisService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', choices=('north', 'south', 'east'), required=True)
    parser.add_argument('--video', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--config')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--profile', default='operating')
    parser.add_argument('--end', type=float)
    args = parser.parse_args()
    with AnalysisService() as service:
        job = service.start(owner='python-example', restroom_id=args.room, config_path=args.config,
                            video_path=args.video, model_path=args.model, output_dir=args.output,
                            device=args.device, profile=args.profile, end=args.end)
        try:
            for record in job.records():
                print(json.dumps(record, ensure_ascii=False), flush=True)
        except KeyboardInterrupt:
            job.stop()
        state = job.status()
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0 if state['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
