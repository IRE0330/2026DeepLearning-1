import argparse
import json
import sys
from .config import load, save, template, validate


def main(argv=None):
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
    batch = sub.add_parser("batch", help="명시적으로 등록한 모든 영상 순차 분석·화장실별 날짜별 CSV 저장")
    batch.add_argument("--registry", default="configs/video_registry.json")
    batch.add_argument("--profile", default="operating", help="operating, demo 또는 별도 프로필 JSON 경로")
    batch.add_argument("--limit-seconds", type=float, help="각 영상 분석 시작부터 처리할 최대 길이(짧은 점검용)")
    batch.add_argument("--device")
    batch.add_argument("--output-dir", default="outputs")
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
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
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
            print(analyze(args.config, args.start, args.end, args.command == "baseline", args.device,
                          config_override=c))
        elif args.command == "batch":
            from .batch import run_batch
            out = run_batch(args.registry, args.profile, args.limit_seconds, args.device, args.output_dir)
            with (out / "batch_summary.json").open(encoding="utf-8") as f:
                if json.load(f)["failed_count"]:
                    return 2
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
