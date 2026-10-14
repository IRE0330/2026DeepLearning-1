"""OpenCV mouse editor. Save requires explicit review of the complete preview."""
import copy
from .config import load, save, validate, resolve
from .media import frame_at, image_write
from .overlay import draw_zones

ITEMS = ["boundary", "entry_direction", "outside_zone", "inside_zone", "waiting_zone",
         "transit_zone", "excluded_zones"]


def edit(config_path, time_s=0, max_width=1280, max_height=720):
    import cv2
    c = load(config_path)
    frame, actual_time = frame_at(c["video"], time_s)
    h, w = frame.shape[:2]
    # Reserve the help footer inside the requested total window height.
    scale = min(1, max_width / w, (max_height - 115) / h)
    dw, dh = max(1, round(w * scale)), max(1, round(h * scale))
    c["reference_size"], c["configured"] = [w, h], False
    c["configuration_frame_time_s"] = actual_time
    selected, points, reviewed, message = 0, [], False, "Click points; N commits item."
    window = "CCTV zone editor"
    try:
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        def mouse(event, x, y, flags, param):
            nonlocal reviewed
            if event == cv2.EVENT_LBUTTONDOWN and 0 <= x < dw and 0 <= y < dh:
                # Original point = (x*w/dw, y*h/dh), normalized by (w,h).
                points.append([x / dw, y / dh])
                reviewed = False
            elif event == cv2.EVENT_RBUTTONDOWN:
                if points:
                    points.pop()
                reviewed = False
        cv2.setMouseCallback(window, mouse)
        while True:
            canvas = draw_zones(frame.copy(), c)
            display = cv2.resize(canvas, (dw, dh))
            for p in points:
                cv2.circle(display, (round(p[0] * dw), round(p[1] * dh)), 5, (0, 255, 0), -1)
            for a, b in zip(points, points[1:]):
                cv2.line(display, (round(a[0] * dw), round(a[1] * dh)),
                         (round(b[0] * dw), round(b[1] * dh)), (0, 255, 0), 2)
            footer = __import__("numpy").zeros((115, dw, 3), dtype="uint8")
            lines = [f"Item {selected + 1}/7: {ITEMS[selected]}  points={len(points)}",
                     "N: commit/next  Tab: next  B: previous  U/right-click: undo  R: clear item",
                     "P: validate & review preview  S: save after P  Q/Esc: exit without saving",
                     message[:max(40, dw // 8)]]
            for i, line in enumerate(lines):
                cv2.putText(footer, line, (8, 24 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imshow(window, __import__("numpy").vstack([display, footer]))
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                return False
            if key == ord("u"):
                if points:
                    points.pop()
                reviewed = False
            elif key == ord("r"):
                points.clear()
                c[ITEMS[selected]] = []
                reviewed = False
            elif key in (9, ord("b")):
                selected = (selected + (1 if key == 9 else -1)) % len(ITEMS)
                points.clear()
                reviewed = False
            elif key == ord("n"):
                name = ITEMS[selected]
                if name == "excluded_zones":
                    if len(points) >= 3:
                        c[name].append(copy.deepcopy(points))
                        points.clear()
                        message = "Excluded polygon added; N with no points advances."
                    elif not points:
                        selected = 0
                    else:
                        message = "Polygon needs 3 or more points."
                elif (len(points) == 2 if name in ITEMS[:2] else len(points) >= 3):
                    c[name] = copy.deepcopy(points)
                    selected = (selected + 1) % len(ITEMS)
                    points.clear()
                    message = "Item committed."
                elif name == "transit_zone" and not points:
                    selected = 6
                else:
                    message = "Line/arrow needs 2 points; polygon needs 3+."
                reviewed = False
            elif key == ord("p"):
                try:
                    if points:
                        raise ValueError("Commit pending points with N first.")
                    c["configured"] = True
                    validate(c, video_size=(w, h))
                    reviewed = True
                    message = "REVIEW complete overlay. S confirms and saves; Q cancels."
                except ValueError as exc:
                    c["configured"] = False
                    message = str(exc)
                    print(exc)
            elif key == ord("s"):
                if reviewed:
                    c["confirmed_by_user"] = True
                    save(c, config_path)
                    image_write(str(resolve(config_path).with_suffix(".preview.jpg")), draw_zones(frame.copy(), c))
                    print(f"구역 저장 완료: {config_path}")
                    return True
                message = "Press P and review before saving."
    except cv2.error as exc:
        raise RuntimeError("GUI를 열지 못했습니다. 데스크톱 PowerShell에서 configure를 실행하거나 확인된 JSON 설정을 사용하세요.") from exc
    finally:
        cv2.destroyAllWindows()
