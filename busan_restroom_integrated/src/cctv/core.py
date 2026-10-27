"""Deterministic state transitions using video time, no CV/model dependencies."""
from collections import deque
from dataclasses import dataclass, field
import math
from .geometry import in_polygon, line_distance, segments_intersect
from .usage import queue_estimates


@dataclass
class Observation:
    track_id: int
    box: tuple
    confidence: float = 1.0

    @property
    def point(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2, y2)

    @property
    def height(self):
        return max(self.box[3] - self.box[1], 1.0)


@dataclass
class TrackState:
    last_t: float = -1
    point: tuple | None = None
    height: float = 1
    missing: bool = False
    origin: str | None = None
    zone: str | None = None
    side_elapsed: float = 0
    pending: dict | None = None
    wait: str = "nonwaiting"
    slow_elapsed: float = 0
    exit_elapsed: float = 0
    history: deque = field(default_factory=deque)


class Counter:
    def __init__(self, config, width, height):
        self.c = config
        self.r = config["rules"]
        self.width, self.height = width, height
        self.tracks = {}
        self.enter = self.exit = 0
        self.events = []
        self.diagnostics = []
        self.last_time = None
        self.anomalies = {"negative_inside_transitions": 0,
                          "observation_gap_resets": 0, "grace_suppression_frames": 0,
                          "unconfirmed_crossings": 0}
        self.negative_before = False
        self.inside_sign = 1 if line_distance(config["entry_direction"][1], config["boundary"]) > 0 else -1

    def log(self, kind, t, tid=None, **data):
        self.diagnostics.append({"kind": kind, "video_time_s": t, "track_id": tid, **data})

    def normalized(self, p):
        return p[0] / self.width, p[1] / self.height

    def region(self, p):
        distance = line_distance(p, self.c["boundary"]) * self.inside_sign
        if distance > self.r["boundary_margin"] and in_polygon(p, self.c["inside_zone"]):
            return "inside"
        if distance < -self.r["boundary_margin"] and in_polygon(p, self.c["outside_zone"]):
            return "outside"
        return None

    def clear_path(self, s):
        s.origin = s.zone = s.pending = None
        s.side_elapsed = 0
        s.history.clear()
        s.slow_elapsed = s.exit_elapsed = 0
        if s.wait != "confirmed":
            s.wait = "nonwaiting"

    def cancel_pending(self, s, t, tid, reason):
        if s.pending:
            self.anomalies["unconfirmed_crossings"] += 1
            self.log("crossing_candidate_cancelled", t, tid, reason=reason, pending=dict(s.pending))
            s.pending = None

    def update(self, t, frame_index, observations):
        if not math.isfinite(t) or (self.last_time is not None and t <= self.last_time):
            raise ValueError("영상 시각은 유한하고 엄격히 증가해야 합니다.")
        self.last_time = t
        ids = [o.track_id for o in observations]
        if len(ids) != len(set(ids)):
            raise ValueError("한 프레임에 같은 추적 ID가 두 번 존재합니다.")
        self.diagnostics = []
        frame_events = []
        observed = set()
        for o in observations:
            tid, p = o.track_id, self.normalized(o.point)
            s = self.tracks.get(tid)
            if s is None:
                s = self.tracks[tid] = TrackState()
                self.log("first_observed", t, tid)
            dt = t - s.last_t if s.last_t >= 0 else 0
            gap = s.last_t >= 0 and dt > self.r["max_observation_gap_s"] + 1e-9
            was_missing = s.missing
            if was_missing:
                self.log("reobserved_same_tracker_id", t, tid, gap_s=dt)
            if gap or was_missing:
                self.log("crossing_unconfirmed_after_gap", t, tid, gap_s=dt,
                         previous_origin=s.origin, pending=s.pending)
                self.anomalies["observation_gap_resets"] += 1
                self.cancel_pending(s, t, tid, "observation_gap")
                self.clear_path(s)
                if dt > self.r["occlusion_grace_s"]:
                    s.wait = "nonwaiting"
                dt = 0
            wait_dt = 0 if was_missing else dt
            previous_wait, previous_zone = s.wait, s.zone
            excluded = any(in_polygon(p, poly) for poly in self.c["excluded_zones"])
            if excluded:
                self.cancel_pending(s, t, tid, "excluded_point")
                self.clear_path(s)
                s.wait = "nonwaiting"
            else:
                observed.add(tid)
                zone = self.region(p)
                if s.point is not None and not gap and not was_missing and s.origin:
                    prev = self.normalized(s.point)
                    d0 = line_distance(prev, self.c["boundary"]) * self.inside_sign
                    d1 = line_distance(p, self.c["boundary"]) * self.inside_sign
                    if d0 * d1 <= 0 and abs(d1 - d0) > 1e-9 and segments_intersect(prev, p, *self.c["boundary"]):
                        destination = "inside" if d1 > d0 else "outside"
                        if destination != s.origin:
                            fraction = abs(d0) / (abs(d0) + abs(d1))
                            s.pending = {"destination": destination,
                                         "crossing_time_estimate_s": s.last_t + fraction * (t - s.last_t),
                                         "crossing_position": [prev[i] + fraction * (p[i] - prev[i]) for i in (0, 1)]}
                            self.log("finite_boundary_crossed_candidate", t, tid, **s.pending)
                        else:
                            self.cancel_pending(s, t, tid, "crossed_back_toward_origin")
                s.side_elapsed = s.side_elapsed + (0 if was_missing else dt) if zone and zone == s.zone else 0
                s.zone = zone
                entered = False
                if zone and s.side_elapsed + 1e-9 >= self.r["side_confirm_s"]:
                    if s.origin is None:
                        s.origin = zone
                    elif zone != s.origin:
                        if s.pending and s.pending["destination"] == zone:
                            direction = "entry" if zone == "inside" else "exit"
                            event = {"restroom_id": self.c["restroom_id"], "video_time_s": t,
                                     "frame_index": frame_index, "track_id": tid,
                                     "direction": direction, "position_x": o.point[0],
                                     "position_y": o.point[1], **s.pending,
                                     "reason": "confirmed_origin -> finite_segment -> confirmed_destination"}
                            self.events.append(event)
                            frame_events.append(event)
                            self.log("crossing_confirmed", t, tid, event=event)
                            self.enter += direction == "entry"
                            self.exit += direction == "exit"
                            entered = direction == "entry"
                        else:
                            self.log("opposite_region_without_confirmed_crossing", t, tid)
                            self.anomalies["unconfirmed_crossings"] += 1
                        s.origin, s.pending = zone, None
                    else:
                        self.cancel_pending(s, t, tid, "origin_reconfirmed")
                s.history.append((t, o.point, o.height))
                # Keep a preceding point so speed spans the requested window.
                while len(s.history) > 2 and s.history[1][0] < t - self.r["motion_window_s"]:
                    s.history.popleft()
                span = t - s.history[0][0]
                speed = None
                if span + 1e-9 >= self.r["motion_min_span_s"]:
                    path = sum(math.dist(a[1], b[1]) / ((a[2] + b[2]) / 2)
                               for a, b in zip(s.history, list(s.history)[1:]))
                    speed = path / span
                in_wait = in_polygon(p, self.c["waiting_zone"]) and not in_polygon(p, self.c["transit_zone"])
                if entered:
                    s.wait, s.slow_elapsed, s.exit_elapsed = "nonwaiting", 0, 0
                elif in_wait:
                    s.exit_elapsed = 0
                    if s.wait != "confirmed":
                        s.wait = "candidate"
                        # Only adjacent, continuously observed candidate intervals
                        # provide evidence. A rolling path speed additionally prevents
                        # a single low-speed frame after fast motion confirming a wait.
                        segment_speed = (math.dist(s.point, o.point) /
                                         ((s.height + o.height) / 2) / wait_dt
                                         if wait_dt > 0 and s.point is not None else None)
                        if (previous_wait == "candidate" and segment_speed is not None
                                and segment_speed <= self.r["slow_speed_body_heights_s"]):
                            s.slow_elapsed += wait_dt
                        else:
                            s.slow_elapsed = 0
                        if (s.slow_elapsed + 1e-9 >= self.r["waiting_confirm_s"]
                                and speed is not None
                                and speed <= self.r["slow_speed_body_heights_s"]):
                            s.wait = "confirmed"
                else:
                    s.exit_elapsed += wait_dt
                    if s.wait == "candidate" or s.exit_elapsed + 1e-9 >= self.r["zone_exit_s"]:
                        s.wait, s.slow_elapsed = "nonwaiting", 0
                self.log("observation", t, tid, box=list(o.box), confidence=o.confidence,
                         point=list(o.point), normalized_point=p, region=zone,
                         waiting_state=s.wait, slow_evidence_s=s.slow_elapsed,
                         speed_body_heights_s=speed)
            if excluded:
                self.log("excluded_observation", t, tid, box=list(o.box), confidence=o.confidence, point=list(o.point))
            if previous_wait != s.wait or previous_zone != s.zone:
                self.log("state_changed", t, tid, before_wait=previous_wait, after_wait=s.wait,
                         before_region=previous_zone, after_region=s.zone)
            s.point, s.height, s.last_t, s.missing = o.point, o.height, t, False
        all_seen = set(ids)
        for tid, s in list(self.tracks.items()):
            if tid in all_seen:
                continue
            if not s.missing:
                self.log("tracker_id_not_observed", t, tid, last_observed_s=s.last_t)
                s.missing = True
            if t - s.last_t > self.r["occlusion_grace_s"] + 1e-9 and s.wait != "nonwaiting":
                self.log("waiting_grace_expired", t, tid)
                s.wait, s.slow_elapsed = "nonwaiting", 0
            if t - s.last_t > self.r["forget_track_s"]:
                del self.tracks[tid]
        waiting_candidates = sum(self.tracks[tid].wait == "candidate" for tid in observed)
        waiting_confirmed = sum(self.tracks[tid].wait == "confirmed" for tid in observed)
        waiting_observed = waiting_confirmed
        grace, suppressed = 0, []
        for tid, s in self.tracks.items():
            if tid in all_seen or s.wait != "confirmed" or t - s.last_t > self.r["occlusion_grace_s"] + 1e-9:
                continue
            near = [other for other in observed if math.dist(s.point, self.tracks[other].point) <=
                    self.r["duplicate_radius_body_heights"] * max(s.height, self.tracks[other].height)]
            if near:
                suppressed.append(tid)
                self.log("grace_count_suppressed_possible_duplicate", t, tid, nearby_ids=near,
                         identity_claim=False)
            else:
                grace += 1
        if suppressed:
            self.anomalies["grace_suppression_frames"] += 1
        inside = None if self.c["initial_inside"] is None else self.c["initial_inside"] + self.enter - self.exit
        negative = inside is not None and inside < 0
        if negative and not self.negative_before:
            self.anomalies["negative_inside_transitions"] += 1
            self.log("negative_inside", t, value=inside)
        self.negative_before = negative
        status = ["measuring"]
        if inside is None:
            status.append("initial_inside_unset")
        if waiting_candidates:
            status.append("candidate_excluded")
        if grace:
            status.append("confirmed_occlusion_grace")
        if any(s.pending for s in self.tracks.values()):
            status.append("crossing_candidate_pending")
        if self.anomalies["unconfirmed_crossings"]:
            status.append("crossing_unconfirmed_recorded")
        if self.anomalies["observation_gap_resets"]:
            status.append("observation_gap_reset_recorded")
        if negative:
            status.append("negative_inside")
        if suppressed:
            status.append("uncertain_grace_suppressed")
        snapshot = {"restroom_id": self.c["restroom_id"], "source_time_s": t,
                    "frame_index": frame_index, "entries": self.enter, "exits": self.exit,
                    "waiting_observed": waiting_observed, "waiting_grace": grace,
                    "waiting_candidate_observed": waiting_candidates,
                    "waiting_confirmed_observed": waiting_confirmed,
                    "waiting_total": waiting_observed + grace, "grace_suppressed": len(suppressed),
                    "net_inflow": self.enter - self.exit, "inside_estimate": inside,
                    "measurement_status": ";".join(status),
                    **queue_estimates(self.c, inside, waiting_observed + grace)}
        return snapshot, frame_events, list(self.diagnostics)


class SecondSampler:
    """Emit integer timestamps with only the most recent past state."""
    def __init__(self, start_s):
        self.next_second = math.ceil(start_s - 1e-9)
        self.previous = None

    def push(self, snapshot):
        t, rows = snapshot["source_time_s"], []
        while self.next_second < t - 1e-9:
            if self.previous is not None and self.previous["source_time_s"] <= self.next_second:
                rows.append({"sample_time_s": self.next_second, **self.previous})
            self.next_second += 1
        if abs(self.next_second - t) <= 1e-9:
            rows.append({"sample_time_s": self.next_second, **snapshot})
            self.next_second += 1
        self.previous = dict(snapshot)
        return rows
