"""Export locally verified annotations. Existing output files are never replaced."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'busan_restroom_dashboard'))
from distance_reference import REFERENCE_PATH, build_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=ROOT / 'busan_restroom_dashboard/data/settings.json')
    parser.add_argument('--output', type=Path, default=REFERENCE_PATH)
    args = parser.parse_args()
    cfg = json.loads(args.settings.read_text(encoding='utf-8'))
    reference = build_reference(cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(reference, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print('Exported validated annotations for north/east/south. Editor remains visible until verification.')


if __name__ == '__main__':
    main()
