def draw_zones(frame, c):
    import cv2
    import numpy as np
    h, w = frame.shape[:2]
    def pixels(points):
        return np.array([[min(w - 1, round(x * w)), min(h - 1, round(y * h))] for x, y in points], dtype=np.int32)
    for key, color in (("outside_zone", (255, 180, 0)), ("inside_zone", (255, 80, 180)),
                       ("waiting_zone", (0, 220, 220)), ("transit_zone", (180, 180, 180))):
        if c.get(key):
            p = pixels(c[key])
            cv2.polylines(frame, [p], True, color, 2)
            cv2.putText(frame, key, tuple(p[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    for poly in c.get("excluded_zones", []):
        cv2.polylines(frame, [pixels(poly)], True, (0, 0, 255), 2)
    if len(c.get("boundary", [])) == 2:
        p = pixels(c["boundary"])
        cv2.line(frame, tuple(p[0]), tuple(p[1]), (0, 255, 0), 3)
    if len(c.get("entry_direction", [])) == 2:
        p = pixels(c["entry_direction"])
        cv2.arrowedLine(frame, tuple(p[0]), tuple(p[1]), (0, 255, 0), 3, tipLength=0.15)
    return frame


def annotate(frame, c, observations, counter, snapshot, mode="analysis"):
    import cv2
    draw_zones(frame, c)
    for o in observations:
        state = counter.tracks[o.track_id].wait if counter else "tracked"
        color = (0, 255, 255) if state == "confirmed" else (0, 165, 255) if state == "candidate" else (255, 180, 0)
        x1, y1, x2, y2 = map(round, o.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, tuple(map(round, o.point)), 5, (0, 0, 255), -1)
        cv2.putText(frame, f"ID {o.track_id} {state} {o.confidence:.2f}", (x1, max(20, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    from .panel import draw_panel
    return draw_panel(frame, c, snapshot, mode)
