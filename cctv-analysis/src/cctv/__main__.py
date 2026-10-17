import argparse
import json
import sys
import time
from .config import load, save, template, validate


def main(argv=None):
    execution_started_ns = time.perf_counter_ns()
    # Keep Korean messages and paths readable when stdout is captured by an IDE.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="부산역 CCTV 출입·대기 인원 MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="전체 타임스탬프 검사 및 대표 프레임 저장")
    inspect.add_argument("--video", required=True)
    inspect.add_argument("--label", default="video")
    init = sub.add_parser("init", help="좌표 없는 환경 설정 생성")
    init.add_argument("--config", required=True)
    init.add_argument("--id", required=True)
    init.add_argument("--video", required=True)
    editor = sub.add_parser("configure", help="마우스 구역 설정; P 미리보기 후 S 확인 저장")
    editor.add_argument("--config", required=True)
    editor.add_argument("--time", type=float, default=0)
    editor.add_argument("--max-width", type=int, default=1280)
    editor.add_argument("--max-height", type=int, default=720)
    preview = sub.add_parser("preview", help="GUI 없이 설정 오버레이 이미지 저장")
    preview.add_argument("--config", required=True)
    preview.add_argument("--time", type=float, default=0)
    check = sub.add_parser("validate", help="설정 검사")
    check.add_argument("--config", required=True)
    metadata = sub.add_parser("metadata", help="촬영 기준시각·영상 ID·칸 수·이용시간 계산 가정 설정")
    metadata.add_argument("--config", required=True)
    metadata.add_argument("--capture-start")
    metadata.add_argument("--capture-kind", choices=("real", "virtual"))
    metadata.add_argument("--clear-capture-time", action="store_true")
    metadata.add_argument("--bind-video", action="store_true")
    metadata.add_argument("--video-id")
    metadata.add_argument("--available-stalls", type=int)
    metadata.add_argument("--mean-use-seconds", type=float)
    for command in ("analyze", "baseline"):
        runner = sub.add_parser(command, help="출입·대기 분석" if command == "analyze" else "구역 없이 탐지·추적만 실행")
        runner.add_argument("--config", required=True)
        runner.add_argument("--start", type=float, default=0)
        runner.add_argument("--end", type=float)
        runner.add_argument("--device", help="auto, cpu, cuda:0 또는 mps")
        runner.add_argument("--profile", default="operating", help="operating, demo 또는 별도 프로필 JSON 경로")
        runner.add_argument('--prediction', choices=('disabled', 'mock'), help='실제 모델 호출 없이 비활성/로컬 모의 전달 선택')
        runner.add_argument('--csv-split-seconds', type=int, choices=(3600, 86400), help='정시1시간 또는 기존 날짜별 저장')
        runner.add_argument('--no-video', action='store_true', help='오버레이·결과 영상 저장 없이 동일 분석/CSV/진단 유지')
        runner.add_argument('--measure-csv-latency', action='store_true', help='monotonic CSV flush 측정을 별도 파일에 저장')
        runner.add_argument('--output-dir', help='새 고유 실행 폴더를 만들 부모 경로')
        runner.add_argument('--video', help='입력 영상 경로; 지정하면 설정 사본의 영상 ID/해시를 재등록')
        runner.add_argument('--model', help='로컬 가중치 경로')
    batch = sub.add_parser("batch", help="등록 영상 순차 분석·화장실별 시간별 CSV 저장")
    batch.add_argument("--registry", default="configs/video_registry.json")
    batch.add_argument("--profile", default="operating", help="operating, demo 또는 별도 프로필 JSON 경로")
    batch.add_argument("--limit-seconds", type=float, help="각 영상 분석 시작부터 처리할 최대 길이(짧은 점검용)")
    batch.add_argument("--device")
    batch.add_argument("--output-dir", default="outputs")
    batch.add_argument('--prediction', choices=('disabled', 'mock'))
    batch.add_argument('--csv-split-seconds', type=int, choices=(3600, 86400))
    retry = sub.add_parser('deliver-outbox', help='보존된 미전달 레코드를 같은 ID로 로컬 모의 재전달')
    retry.add_argument('--outbox', required=True)
    retry.add_argument('--prediction', choices=('mock',), required=True)
    retry.add_argument('--retry-failed', action='store_true', help='재시도 한도를 소진한 항목도 새 제한 횟수로 재시도')
    retry.add_argument('--shutdown-seconds', type=float)
    sub.add_parser("download-model", help="YOLO11n 가중치 다운로드")
    evaluate = sub.add_parser("evaluate", help="실제 수동 정답으로 평가")
    evaluate.add_argument("--run", required=True)
    evaluate.add_argument("--truth", required=True)
    evaluate.add_argument("--tolerance", type=float, default=1.0)
    micc = sub.add_parser("micc-inspect", help="MICC 구조 점검; 자동 학습/라벨 변환 없음")
    micc.add_argument("--path", default="data/micc_crowd_counting.zip")
    sequence = sub.add_parser("micc-track", help="RGB PNG 연속 프레임 탐지·추적; 초 단위 행동 판정 없음")
    sequence.add_argument("--rgb", required=True)
    sequence.add_argument("--start-frame", type=int, default=0)
    sequence.add_argument("--frames", type=int, default=60)
    sequence.add_argument("--preview-fps", type=float, default=12)
    sequence.add_argument("--device", default="auto")
    sub.add_parser("doctor", help="실제 Python·패키지·장치 정보")
    sub.add_parser('example-path', help='설치된 최소 Streamlit 예시 경로')
    presets = sub.add_parser('preset', help='번들 환경 설정 경로; 사용자 자료는 별도 지정')
    presets.add_argument('restroom_id', choices=('north', 'south', 'east'))
    assets = sub.add_parser('export-assets', help='설정·빈 정답 양식을 새 폴더로 복사; 영상/가중치 제외')
    assets.add_argument('--destination', required=True)
    paced = sub.add_parser('simulate-input', help='고정 monotonic 일정의 저장 영상 입력 모사; 실제 CCTV 아님')
    paced.add_argument('--rooms', nargs='+', choices=('north', 'south', 'east'), default=['north'])
    paced.add_argument('--input-mode', choices=('paced', 'unpaced'), default='paced')
    paced.add_argument('--output-dir', default='outputs')
    paced.add_argument('--end', type=float, help='비교용 부분 구간 종료; 생략하면 전체 길이')
    paced.add_argument('--queue-capacity', type=int, default=8)
    paced.add_argument('--soft-lag-seconds', type=float, default=5.)
    paced.add_argument('--sustained-lag-seconds', type=float, default=10.)
    paced.add_argument('--hard-lag-seconds', type=float, default=15.)
    args = parser.parse_args(argv)
    try:
        if args.command == 'export-assets':
            import shutil
            from pathlib import Path
            from .config import DATA
            target = Path(args.destination).expanduser().resolve()
            if target.exists():
                raise ValueError(f'새 폴더를 지정하세요: {target}')
            shutil.copytree(DATA, target)
            print(target)
        elif args.command == 'example-path':
            from pathlib import Path
            print(Path(__file__).parent / 'examples' / 'streamlit_app.py')
        elif args.command == 'preset':
            from .config import preset_path
            print(preset_path(args.restroom_id))
        elif args.command == 'simulate-input':
            from .paced import run_simulation
            out = run_simulation(args.rooms, args.input_mode, args.output_dir, args.end, args.queue_capacity,
                                 args.soft_lag_seconds, args.sustained_lag_seconds, args.hard_lag_seconds)
            with (out / 'experiment_summary.json').open(encoding='utf-8') as handle:
                if json.load(handle)['status'] != 'completed':
                    return 2
        elif args.command == "init":
            from .config import resolve
            if resolve(args.config).exists():
                raise ValueError("설정 파일이 이미 있습니다. 다른 파일 이름을 사용하세요.")
            c = template(args.id, args.video)
            if resolve(args.video).is_file():
                from .usage import bind_video
                bind_video(c)
            save(c, args.config)
            print(f"미설정 환경 생성: {args.config}")
        elif args.command == "inspect":
            from .media import probe, unique_dir
            out = unique_dir("inspections", args.label)
            print(json.dumps(probe(args.video, out), ensure_ascii=False, indent=2))
            print(f"대표 프레임 폴더: {out}")
        elif args.command == "configure":
            from .configure import edit
            if args.time < 0 or args.max_width < 320 or args.max_height < 240:
                raise ValueError("시각은 0 이상, 화면은 320x240 이상이어야 합니다.")
            edit(args.config, args.time, args.max_width, args.max_height)
        elif args.command == "preview":
            from .media import frame_at, image_write, unique_dir
            from .overlay import draw_zones
            import cv2
            c = load(args.config)
            frame, t = frame_at(c["video"], args.time)
            draw_zones(frame, c)
            label = "CONFIRMED" if c.get("configured") else "UNCONFIRMED - DO NOT USE FOR COUNTS"
            cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            out = unique_dir("inspections", c["restroom_id"] + "_preview")
            image_write(out / "zones.jpg", frame)
            print(f"설정 미리보기: {out / 'zones.jpg'} (영상 시각 {t:.3f}s)")
        elif args.command == "validate":
            validate(load(args.config))
            print("설정 검사 통과")
        elif args.command == "metadata":
            from .usage import bind_video
            c = load(args.config)
            if args.clear_capture_time and (args.capture_start is not None or args.capture_kind is not None):
                raise ValueError("촬영시각 해제와 새 촬영시각 지정은 함께 사용할 수 없습니다.")
            if args.clear_capture_time:
                c.update(capture_start_time=None, capture_time_kind=None)
            if args.capture_start is not None:
                c["capture_start_time"] = args.capture_start
            if args.capture_kind is not None:
                c["capture_time_kind"] = args.capture_kind
            if args.available_stalls is not None:
                c["available_stalls"] = args.available_stalls
            if args.mean_use_seconds is not None:
                c["average_stall_use_s"] = args.mean_use_seconds
            if args.bind_video or args.video_id is not None:
                bind_video(c, args.video_id)
            validate(c, require_zones=False)
            save(c, args.config)
            print("공유 CSV 메타데이터 저장 완료. 구역 좌표는 보존했습니다.")
        elif args.command in ("analyze", "baseline"):
            from .pipeline import analyze
            from .profiles import apply_profile, load_profile
            c = apply_profile(load(args.config), load_profile(args.profile))
            from .config import resolve, LEGACY_ROOT
            if LEGACY_ROOT is None and args.output_dir is None:
                raise ValueError('설치된 패키지 실행에는 쓰기 가능한 --output-dir를 지정하세요.')
            if args.video:
                c['video'] = str(resolve(args.video))
                from .usage import bind_video
                bind_video(c)
            if args.model:
                c['model'] = str(resolve(args.model))
            if args.output_dir:
                c['cache_dir'] = str(resolve(args.output_dir) / '.cache')
            if args.prediction is not None:
                c['prediction_mode'] = args.prediction
            if args.csv_split_seconds is not None:
                c['csv_split_interval_s'] = args.csv_split_seconds
            print(analyze(args.config, args.start, args.end, args.command == "baseline", args.device,
                          config_override=c, output_base=args.output_dir, save_video=not args.no_video,
                          measure_csv_latency=args.measure_csv_latency, execution_started_ns=execution_started_ns,
                          timing_origin='cli_main_entry_excludes_interpreter_and_initial_module_imports'))
        elif args.command == "batch":
            from .batch import run_batch
            out = run_batch(args.registry, args.profile, args.limit_seconds, args.device, args.output_dir,
                            prediction_mode=args.prediction, csv_split_interval_s=args.csv_split_seconds)
            with (out / "batch_summary.json").open(encoding="utf-8") as f:
                if json.load(f)["failed_count"]:
                    return 2
        elif args.command == 'deliver-outbox':
            from .stream_output import retry_outbox
            from .config import resolve
            result, path = retry_outbox(resolve(args.outbox), args.retry_failed, args.shutdown_seconds)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(f'재전달 요약: {path}')
        elif args.command == "download-model":
            from .detector import download_default
            download_default()
        elif args.command == "evaluate":
            from .evaluate import evaluate
            evaluate(args.run, args.truth, args.tolerance)
        elif args.command == "micc-inspect":
            from .micc import inspect_micc
            inspect_micc(args.path)
        elif args.command == "micc-track":
            from .sequence import review_sequence
            review_sequence(args.rgb, args.start_frame, args.frames, args.preview_fps, args.device)
        elif args.command == "doctor":
            from .pipeline import versions
            from .detector import select_device
            from .media import write_json
            from .config import ROOT
            import torch
            data = {**versions(), "python_executable": sys.executable,
                    "cpu_supported": True, "cuda_available": torch.cuda.is_available(),
                    "mps_available": torch.backends.mps.is_available(), "auto_device": select_device("auto"),
                    "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}
            (ROOT / "docs").mkdir(exist_ok=True)
            write_json(ROOT / "docs" / "environment.json", data)
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
