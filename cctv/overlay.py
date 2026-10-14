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
    if mode == "baseline":
        lines = [f"t={snapshot['source_time_s']:.3f}s BASELINE - ZONES NOT CONFIRMED",
                 "Detection + ByteTrack only; no entry/waiting counts"]
    else:
        inside = snapshot["inside_estimate"]
        q, seconds = snapshot.get("total_queue_estimate"), snapshot.get("expected_wait_s")
        status = "MEASURING - accuracy not validated"
        if inside is None:
            status += "; initial inside unknown"
        if "negative_inside" in snapshot["measurement_status"]:
            status += "; negative inside"
        if counter.anomalies.get("unconfirmed_crossings") or any(s.pending for s in counter.tracks.values()):
            status += "; unconfirmed crossing"
        lines = [f"t={snapshot['source_time_s']:.3f}s Entry={snapshot['entries']} Exit={snapshot['exits']}",
                 f"Waiting observed={snapshot['waiting_observed']} (candidate={snapshot['waiting_candidate_observed']} confirmed={snapshot['waiting_confirmed_observed']})",
                 f"External waiting total={snapshot['waiting_total']} grace={snapshot['waiting_grace']} suppressed={snapshot['grace_suppressed']}",
                 f"Net={snapshot['net_inflow']} Inside={'unknown' if inside is None else inside} Q={'unknown' if q is None else q} Assumed wait={'unknown' if seconds is None else f'{seconds:.1f}s'}",
                 f"Estimated internal wait={snapshot.get('internal_waiting_estimate')} Free stalls={snapshot.get('available_stalls_estimate')} (occupancy not observed)",
                 status]
        if c.get("profile_name") == "demo":
            lines.append("DEMO - synthetic capture time and user assumptions; not verified accuracy")
    panel_h = 28 * len(lines) + 10
    cv2.rectangle(frame, (0, 0), (min(frame.shape[1], 950), panel_h), (25, 25, 25), -1)
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (10, 25 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    return frame
