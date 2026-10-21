"""Compact resolution-relative statistics, independent of counting and CSVs."""
from functools import lru_cache
import math
import os
from pathlib import Path
from .config import load

POSITIONS = ("bottom_left", "bottom_right", "top_left", "top_right")


def settings(config):
    result = load('configs/overlay.json')
    result = {**result, **result.get("environments", {}).get(config.get("restroom_id"), {}),
              **config.get("overlay", {})}
    result.setdefault("position", "bottom_left")
    for key, default, low, high in (("width_ratio", .35, .2, .36),
                                   ("height_ratio", .22, .15, .23),
                                   ("margin_ratio", .01, 0, .1), ("opacity", .78, .1, .95)):
        result.setdefault(key, default)
        value = result[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"overlay.{key} must be between {low} and {high}")
    if result["position"] not in POSITIONS:
        raise ValueError("overlay.position: " + ", ".join(POSITIONS))
    return result


def geometry(width, height, config):
    options = settings(config)
    w, h = round(width * options["width_ratio"]), round(height * options["height_ratio"])
    margin = round(width * options["margin_ratio"])
    x = margin if options["position"].endswith("left") else width - margin - w
    y = margin if options["position"].startswith("top") else height - margin - h
    return {"x": max(0, x), "y": max(0, y), "width": w, "height": h, **options}


@lru_cache(maxsize=1)
def font_paths():
    root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    choices = [(root / "malgun.ttf", root / "malgunbd.ttf"),
               (Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
                Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"))]
    for regular, bold in choices:
        if regular.is_file():
            return str(regular), str(bold if bold.is_file() else regular), "ko"
    return "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "en"


@lru_cache(maxsize=64)
def font(size, bold=False):
    from PIL import ImageFont
    regular, heavy, _ = font_paths()
    return ImageFont.truetype(heavy if bold else regular, max(1, size))


def panel_text(config, state, mode="analysis"):
    korean = font_paths()[2] == "ko"
    elapsed = max(0, int(state["source_time_s"]))
    time = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
    room = config.get("restroom_id", "")
    demo = config.get("profile_name") == "demo"
    def value(key, unit="", decimal=False):
        v = state.get(key)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return "—"
        return (f"{v:.1f}" if decimal else str(v)) + unit
    if korean:
        title = f"{ {'north': '북쪽', 'south': '남쪽', 'east': '동쪽'}.get(room, room)} · {time} · {'시연·미검증' if demo else '미검증'}"
        rows = [(f"입장 {value('entries', '명')}", f"퇴장 {value('exits', '명')}"),
                (f"내부 {value('inside_estimate', '명')}", f"빈 칸 {value('available_stalls_estimate', '칸')}"),
                (f"외부 대기 {value('waiting_total', '명')}", f"내부 대기 {value('internal_waiting_estimate', '명')}"),
                (f"전체 대기 {value('total_queue_estimate', '명')}", f"예상 {value('expected_wait_s', '초', True)}")]
        notes = ["인원·빈 칸·시간은 추정"]
        if state.get("inside_estimate") is None:
            notes.append("초기 인원 미설정")
        if "negative_inside" in state.get("measurement_status", ""):
            notes.append("내부 음수")
        if "crossing_candidate_pending" in state.get("measurement_status", ""):
            notes.append("출입 미확정")
        if mode == "baseline":
            notes = ["탐지·추적 전용 · 집계 없음"]
    else:
        title = f"{room.title()} · {time} · {'Demo / unvalidated' if demo else 'Unvalidated'}"
        rows = [(f"In {value('entries')}", f"Out {value('exits')}"),
                (f"Inside {value('inside_estimate')}", f"Free {value('available_stalls_estimate')}"),
                (f"Outside queue {value('waiting_total')}", f"Inside queue {value('internal_waiting_estimate')}"),
                (f"Total queue {value('total_queue_estimate')}", f"Wait {value('expected_wait_s', 's', True)}")]
        notes = ["People / free stalls / time: estimates"]
        if state.get("inside_estimate") is None:
            notes.append("Initial count unset")
        if "negative_inside" in state.get("measurement_status", ""):
            notes.append("Negative inside")
        if "crossing_candidate_pending" in state.get("measurement_status", ""):
            notes.append("Crossing pending")
        if mode == "baseline":
            notes = ["Detection / tracking only; no counts"]
    return title, rows, " · ".join(notes)


def draw_panel(frame, config, state, mode="analysis"):
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
    height, width = frame.shape[:2]
    g = geometry(width, height, config)
    x, y, w, h = (g[k] for k in ("x", "y", "width", "height"))
    roi = frame[y:y + h, x:x + w]
    # Blend only this ROI; every pixel outside the panel is left untouched.
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    canvas = Image.fromarray(rgb)
    canvas = Image.blend(canvas, Image.new("RGB", canvas.size, (16, 24, 32)), g["opacity"])
    draw = ImageDraw.Draw(canvas)
    pad = max(2, round(width * .008))
    gap = max(2, round(width * .012))
    cell = (w - 2 * pad - gap) // 2
    title, rows, note = panel_text(config, state, mode)
    def fit(texts, size, available, bold=False):
        while size > 1:
            face = font(size, bold)
            if all(draw.textlength(t, font=face) <= available for t in texts):
                return face
            size -= 1
        return font(1, bold)
    heading = fit([title], max(1, round(width * .014)), w - 2 * pad, True)
    body = fit([text for row in rows for text in row], max(1, round(width * .014)), cell)
    footer = fit([note], max(1, round(width * .009)), w - 2 * pad)
    title_h = round(h * .19)
    row_h = (h - 2 * pad - title_h - footer.size - 3) / 4
    draw.text((pad, pad), title, font=heading, fill=(116, 207, 246), anchor="lt")
    for i, row in enumerate(rows):
        top = round(pad + title_h + row_h * i)
        for col, text in enumerate(row):
            draw.text((pad + col * (cell + gap), top), text, font=body,
                      fill=(133, 231, 201) if i == 3 and col == 0 else (245, 247, 250), anchor="lt")
    draw.text((pad, h - pad - footer.size), note, font=footer, fill=(195, 205, 216), anchor="lt")
    frame[y:y + h, x:x + w] = cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)
    return frame
