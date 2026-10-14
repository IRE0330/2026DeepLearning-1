"""Read-only archive/directory inventory; no label conversion or training."""
from collections import Counter
from pathlib import Path
import zipfile
from .config import resolve
from .media import unique_dir, write_json


def inspect_micc(path):
    source = resolve(path)
    out = unique_dir("inspections", "micc")
    report = {"source": str(source), "status": "incomplete", "training_performed": False,
              "detection_tracking_review_completed": False, "quantitative_metrics": None}
    if not source.exists():
        report["reason"] = "자료가 없습니다. 실제 MICC 자료를 data 아래에 준비하세요."
    elif source.is_file():
        report["file_size_bytes"] = source.stat().st_size
        try:
            with zipfile.ZipFile(source) as archive:
                names = [i.filename for i in archive.infolist() if not i.is_dir()]
                report.update(inventory(names))
                report["status"] = "inventory_only"
                # Read only small human-readable annotation candidates, without interpretation.
                report["annotation_text_previews"] = {}
                for n in report["annotation_candidates"][:5]:
                    if Path(n).suffix.lower() in (".txt", ".csv", ".xml", ".json") and archive.getinfo(n).file_size <= 10000:
                        report["annotation_text_previews"][n] = archive.read(n).decode("utf-8", errors="replace")[:2000]
        except (zipfile.BadZipFile, OSError) as exc:
            report["reason"] = f"ZIP 디렉터리를 읽을 수 없습니다: {type(exc).__name__}: {exc}. 다운로드/복사 완료 여부를 확인하세요."
    else:
        names = [str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()]
        report.update(inventory(names))
        report["status"] = "inventory_only"
        report["directory_details"] = directory_details(source)
    report["next_steps"] = ["FLOW/QUEUE/GROUPS의 실제 RGB 영상과 원래 FPS/시간 정보 확인",
                            "정답이 머리/전신 박스인지, 프레임 인원/추적 ID인지 직접 확인",
                            "확인된 RGB 영상에 baseline 실행 후 이동/줄서기/밀집 구간의 diagnostics.jsonl 검토",
                            "탐지 누락·ID 유실 의심 사례를 수동 기록; 확인된 정답 형식에 한해 정량 평가",
                            "이미지 시퀀스에 원래 FPS가 없으면 초 단위 대기 판정을 검증하지 않음"]
    write_json(out / "micc_inventory.json", report)
    print(f"MICC 상태: {report['status']}; 보고서: {out / 'micc_inventory.json'}")
    return out


def inventory(names):
    annotations = [n for n in names if not Path(n).name.startswith(".") and Path(n).suffix.lower() in (".txt", ".csv", ".xml", ".json", ".mat", ".npy", ".dat")]
    sequences = {key: [n for n in names if key in n.upper()][:20] for key in ("FLOW", "QUEUE", "GROUPS")}
    return {"file_count": len(names), "extension_counts": dict(Counter(Path(n).suffix.lower() for n in names)),
            "sample_paths": names[:50], "sequence_name_candidates": sequences,
            "annotation_candidates": annotations[:50],
            "format_verified": False, "fps_verified": False,
            "note": "이름/확장자는 후보 목록이며 RGB·정답 의미·원래 FPS를 확인한 결과가 아닙니다."}


def numeric_files(folder, suffix):
    """Ignore macOS metadata; numeric order rather than 0, 1, 10, 100."""
    return sorted((p for p in folder.glob('*' + suffix) if p.stem.isdecimal()),
                  key=lambda p: int(p.stem))


def directory_details(source):
    import cv2
    import numpy as np
    docs = {str(p.relative_to(source)): p.read_text(encoding="utf-8", errors="replace")[:12000]
            for p in source.rglob("*") if p.is_file() and not p.name.startswith('.')
            and p.suffix.lower() in ('.txt', '.m') and p.stat().st_size < 100000}
    sequences = {}
    for rgb in sorted(source.rglob('RGB')):
        if rgb.parent.name.upper() not in ('FLOW', 'QUEUE', 'GROUPS'):
            continue
        seq = rgb.parent
        item = {}
        for label, folder, suffix in [('rgb', rgb, '.png'), ('depth', seq / 'depth', '.png'),
                                      ('ground_truth', seq / 'GT_dat', '.dat')]:
            files = numeric_files(folder, suffix)
            indices = [int(p.stem) for p in files]
            detail = {'path': str(folder.relative_to(source)), 'file_count': len(files),
                      'first_frame': indices[0] if indices else None,
                      'last_frame': indices[-1] if indices else None,
                      'missing_frame_numbers': sorted(set(range(indices[0], indices[-1] + 1)) - set(indices)) if indices else []}
            if files and suffix == '.png':
                frame = cv2.imdecode(np.fromfile(str(files[0]), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                detail['sample'] = {'file': files[0].name, 'shape': list(frame.shape), 'dtype': str(frame.dtype)}
            if suffix == '.dat':
                samples = []
                counts = Counter()
                for p in files:
                    rows = [line.split() for line in p.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
                    counts.update(len(row) for row in rows)
                    if rows and len(samples) < 3:
                        samples.append({'file': p.name, 'row_count': len(rows), 'first_rows': rows[:5]})
                detail.update(nonempty_samples=samples, row_column_counts=dict(counts))
            item[label] = detail
        item['same_numeric_frame_sets'] = (set(p.stem for p in numeric_files(rgb, '.png')) ==
            set(p.stem for p in numeric_files(seq / 'depth', '.png')) ==
            set(p.stem for p in numeric_files(seq / 'GT_dat', '.dat')))
        sequences[seq.name] = item
    head_documented = any('Head locations' in t or 'bounding box of the head' in t for t in docs.values())
    return {'sequences': sequences, 'description_and_evaluation_sources': docs,
            'annotation_meaning': 'head rectangles: x_top_left y_top_left width height' if head_documented else 'unverified',
            'annotation_evidence': 'readme.txt and evaluation_code/README.txt; actual GT_dat row samples',
            'full_body_boxes': False if head_documented else None,
            'tracking_ids': 'no ID column in sampled four-column GT_dat; persistent identities unverified',
            'person_counts': 'evaluation code counts annotated head rows; no separate count scalar verified',
            'original_fps': None, 'fps_verified': False,
            'time_information': 'No source FPS/timestamps identified in included descriptions/evaluation scripts; filesystem dates are not capture times',
            'depth_units_and_alignment': 'unverified; PNG dtype does not establish units or RGB alignment',
            'toilet_behavior_ground_truth': False}
