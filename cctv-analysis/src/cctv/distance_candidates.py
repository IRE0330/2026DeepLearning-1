"""Distance-demo evidence only. Never changes Counter wait states or counts."""
from collections import deque
import math
from .geometry import in_polygon

DWELL_SECONDS = 2.0


class DistanceCandidates:
    def __init__(self, config, width, height):
        self.config, self.width, self.height = config, width, height
        self.history = {}
        self.confirmed_roi_ids = []

    def update(self, t, observations, tracks):
        c = self.config
        allowed = {}
        for o in observations:
            p = (o.point[0]/self.width, o.point[1]/self.height)
            if (in_polygon(p,c['waiting_zone']) and not in_polygon(p,c['transit_zone'])
                    and not any(in_polygon(p,z) for z in c['excluded_zones'])
                    and tracks[o.track_id].wait in ('candidate','confirmed')):
                allowed[o.track_id] = o
        self.confirmed_roi_ids = [tid for tid in allowed if tracks[tid].wait=='confirmed']
        # Any missing observation or leaving the ROI breaks continuous evidence.
        for tid in list(self.history):
            if tid not in allowed:
                del self.history[tid]
        for tid,o in allowed.items():
            history=self.history.setdefault(tid,deque())
            if history and t-history[-1][0]>c['rules']['max_observation_gap_s']+1e-9:
                history.clear()
            history.append((t,o.point,o.height))
            while len(history)>2 and history[1][0]<=t-DWELL_SECONDS+1e-9:
                history.popleft()

        def motion(tid):
            h=list(self.history[tid]);span=t-h[0][0]
            height=sum(x[2] for x in h)/len(h)
            path=sum(math.dist(a[1],b[1])/((a[2]+b[2])/2) for a,b in zip(h,h[1:]))
            speed=path/span if span>0 else None
            velocity=tuple((h[-1][1][i]-h[0][1][i])/height/span for i in (0,1)) if span>0 else (0.,0.)
            return span,speed,velocity

        result=[]
        for tid,o in allowed.items():
            if tracks[tid].wait!='candidate':
                continue
            span,speed,velocity=motion(tid)
            included=False;reason='insufficient_continuous_dwell';anchor=None
            if span+1e-9>=DWELL_SECONDS and speed is not None:
                if speed<=c['rules']['slow_speed_body_heights_s']:
                    included=True;reason='slow_roi_dwell_2s'
                else:
                    reason='moving_without_queue_evidence'
                    # A moving candidate needs an independently CONFIRMED nearby
                    # anchor observed throughout the same two-second window.
                    for other,a in allowed.items():
                        if tracks[other].wait!='confirmed':continue
                        a_span,a_speed,a_velocity=motion(other)
                        near=math.dist(o.point,a.point)<=2*max(o.height,a.height)
                        vnorm,anorm=math.hypot(*velocity),math.hypot(*a_velocity)
                        aligned=(vnorm>.02 and anorm>.02 and sum(x*y for x,y in zip(velocity,a_velocity))/(vnorm*anorm)>=.8)
                        if (a_span+1e-9>=DWELL_SECONDS and near and aligned
                                and speed<=.7 and a_speed<=.7
                                and math.dist(velocity,a_velocity)<=.15):
                            included=True;reason='co_moving_with_confirmed_queue_2s';anchor=other;break
            result.append({'track_id':tid,'point':[o.point[0]/self.width,o.point[1]/self.height],
                           'confidence':o.confidence,'in_waiting_roi':True,'dwell_s':span,
                           'speed_body_heights_s':speed,'included':included,'reason':reason,
                           'anchor_track_id':anchor})
        return result
