"""Replay saved observations and overlay a selected track on source frames.

Read-only with respect to configurations, existing runs and model parameters.
No inference rerun, coordinate fitting, identity merging or truth generation.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import av
import cv2
import numpy as np
from cctv.config import load, resolve
from cctv.core import Counter, Observation
from cctv.geometry import line_distance, in_polygon
from cctv.media import unique_dir, write_json, image_write, verify_output
from cctv.overlay import draw_zones


def review(run, track_id=6, start=6, end=10):
    run = resolve(run)
    c = json.loads((run / 'config_used.json').read_text(encoding='utf-8'))
    # Saved configs retain repository-relative material paths after final relocation.
    for key in ('video', 'model'):
        if c.get(key) and not Path(c[key]).is_absolute():
            c[key] = str(Path(__file__).resolve().parents[1] / c[key])
    summary = load(run / 'summary.json')
    fps = summary['input_video']['fps']
    width, height = c['reference_size']
    out = unique_dir('inspections', f"{c['restroom_id']}_id{track_id}_review")
    write_json(out / 'config_used.json', c)
    groups = {}
    for line in (run / 'diagnostics.jsonl').open(encoding='utf-8'):
        r = json.loads(line)
        groups.setdefault(r['frame_index'], []).append(r)
    counter = Counter(c, width, height)
    evidence, transitions, target = [], [], {}
    def state(s):
        return {'origin': s.origin, 'region': s.zone, 'side_elapsed_s': s.side_elapsed,
                'pending': None if s.pending is None else dict(s.pending), 'missing': s.missing} if s else None
    for index, logs in sorted(groups.items()):
        t = index / fps
        observations = [Observation(r['track_id'], tuple(r['box']), r['confidence'])
                        for r in logs if r['kind'] in ('observation', 'excluded_observation')]
        before = state(counter.tracks.get(track_id))
        snapshot, events, replay_logs = counter.update(t, index, observations)
        after = state(counter.tracks.get(track_id))
        if not start <= t <= end:
            continue
        row = next((r for r in logs if r.get('track_id') == track_id and r['kind'] in ('observation', 'excluded_observation')), None)
        if row:
            target[index] = row
        point = row['point'] if row else None
        normalized = counter.normalized(point) if point else None
        pending_before = before['pending'] if before else None
        pending_after = after['pending'] if after else None
        reason = None
        if pending_before and not pending_after:
            if any(e['track_id'] == track_id for e in events):
                reason = 'confirmed_event'
            elif any(r['kind'] == 'crossing_unconfirmed_after_gap' and r.get('track_id') == track_id for r in replay_logs):
                reason = 'unconfirmed_observation_gap_reset'
            elif row and row['kind'] == 'excluded_observation':
                reason = 'excluded_point_reset'
            elif before['origin'] == after['origin'] and normalized:
                prev = target.get(index - 1)
                if prev and line_distance(counter.normalized(prev['point']), c['boundary']) * line_distance(normalized, c['boundary']) <= 0:
                    reason = 'crossed_back_toward_origin'
                else:
                    reason = 'origin_confirmation_or_region_transition'
        evidence.append({'frame_index': index, 'video_time_s': t, 'observed': row is not None,
                         'point_x': point[0] if point else None, 'point_y': point[1] if point else None,
                         'logged_region': row.get('region') if row else None,
                         'replay_region': after['region'] if after else None,
                         'side_elapsed_s': after['side_elapsed_s'] if after else None,
                         'origin': after['origin'] if after else None,
                         'pending_destination': pending_after['destination'] if pending_after else None,
                         'pending_removed_reason': reason,
                         'boundary_signed_distance': line_distance(normalized, c['boundary']) * counter.inside_sign if point else None,
                         'inside_polygon': in_polygon(normalized, c['inside_zone']) if point else None,
                         'confidence': row['confidence'] if row else None})
        if before != after and (reason or pending_before != pending_after):
            transitions.append({'video_time_s': t, 'before': before, 'after': after, 'pending_removed_reason': reason,
                                'original_logs': [r for r in logs if r.get('track_id') == track_id and r['kind'] != 'observation']})
    with (out / 'track_state.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(evidence[0]))
        writer.writeheader()
        writer.writerows(evidence)
    points = {i: (round(r['point'][0]), round(r['point'][1])) for i,r in target.items()}
    crop = (160, 55, 455, 365)
    colors = {'inside': (255, 40, 220), 'outside': (255, 200, 0), None: (0, 165, 255)}
    raw_frames, overlays, tiles = {}, {}, []
    writers = {name: cv2.VideoWriter(str(out / name), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width,height))
               for name in ('source_6_10.mp4', 'track_overlay_6_10.mp4')}
    if not all(w.isOpened() for w in writers.values()):
        raise RuntimeError('검토 영상 출력에 실패했습니다.')
    try:
        with av.open(str(resolve(c['video']))) as container:
            for i, decoded in enumerate(container.decode(video=0)):
                t = i / fps
                if t < start:
                    continue
                if t > end:
                    break
                raw = decoded.to_ndarray(format='bgr24')
                raw_frames[i] = raw
                canvas = draw_zones(raw.copy(), c)
                visible = [j for j in sorted(points) if j <= i]
                for a,b in zip(visible, visible[1:]):
                    if b == a+1:
                        cv2.line(canvas, points[a], points[b], (220,220,220), 1)
                for j in visible:
                    cv2.circle(canvas, points[j], 2, colors[target[j].get('region')], -1)
                row = target.get(i)
                if row:
                    x1,y1,x2,y2 = map(round, row['box'])
                    cv2.rectangle(canvas,(x1,y1),(x2,y2),(0,255,255),2)
                    cv2.circle(canvas,points[i],5,(0,255,255),-1)
                cv2.putText(canvas, f'Source {t:.3f}s | Track {track_id} | boxes are not ground truth', (10,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
                overlays[i] = canvas
                writers['source_6_10.mp4'].write(raw)
                writers['track_overlay_6_10.mp4'].write(canvas)
                x1,y1,x2,y2 = crop
                # Consecutive source-frame crops with only the target's logged box and anchor.
                tile = raw[y1:y2,x1:x2].copy()
                if row:
                    bx1,by1,bx2,by2 = map(round,row['box'])
                    cv2.rectangle(tile,(bx1-x1,by1-y1),(bx2-x1,by2-y1),(0,255,255),1)
                    cv2.circle(tile,(points[i][0]-x1,points[i][1]-y1),3,(0,0,255),-1)
                tile = cv2.copyMakeBorder(tile,25,0,0,0,cv2.BORDER_CONSTANT)
                cv2.putText(tile, f'{t:.3f}s frame {i} {row.get("region") if row else "MISSING"}',(5,18),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
                tiles.append(tile)
    finally:
        for writer in writers.values():
            writer.release()
    for page in range((len(tiles)+23)//24):
        cells = tiles[page*24:(page+1)*24]
        cells += [np.zeros_like(tiles[0]) for _ in range(24-len(cells))]
        image_write(out / f'consecutive_{page+1:02d}.jpg', np.vstack([np.hstack(cells[i:i+6]) for i in range(0,24,6)]))
    key_indices = [144,164,169,170,171,173,175,177,180,189,200,210,216,228,239,240]
    selected_raw, selected_overlay = [], []
    for i in key_indices:
        if i not in raw_frames:
            continue
        for collection, frame in ((selected_raw,raw_frames[i]),(selected_overlay,overlays[i])):
            x1,y1,x2,y2 = crop
            tile=frame[y1:y2,x1:x2].copy()
            tile=cv2.copyMakeBorder(tile,25,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(tile,f'{i/fps:.3f}s frame {i}',(5,18),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            collection.append(tile)
    for name, cells in [('keyframes_source.jpg',selected_raw),('keyframes_zones_track.jpg',selected_overlay)]:
        image_write(out/name,np.vstack([np.hstack(cells[i:i+4]) for i in range(0,len(cells),4)]))
    overview = draw_zones(raw_frames[min(raw_frames)].copy(),c)
    for a,b in zip(sorted(points),sorted(points)[1:]):
        if b==a+1:
            cv2.line(overview,points[a],points[b],(240,240,240),1)
    for i,p in points.items():
        cv2.circle(overview,p,3,colors[target[i].get('region')],-1)
    for i in (144,170,171,175,177,189,210,216,239):
        if i in points:
            cv2.putText(overview,f'{i/fps:.3f}s',points[i],cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
    image_write(out/'trajectory_full.jpg',overview)
    x1,y1,x2,y2=crop
    image_write(out/'trajectory_crop.png',cv2.resize(overview[y1:y2,x1:x2],None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST))
    # Geometry-only upper bound: keep the same boundary and margin, omit only
    # polygon membership. This is a diagnostic, not an alternate count result.
    spans, beginning, previous = [], None, None
    for row in evidence:
        valid = row['observed'] and row['boundary_signed_distance'] > c['rules']['boundary_margin']
        if valid:
            if beginning is None or row['frame_index'] != previous['frame_index']+1:
                beginning = row['video_time_s']
            previous = row
        else:
            if beginning is not None:
                spans.append([beginning, previous['video_time_s']])
            beginning = previous = None
    if beginning is not None:
        spans.append([beginning, previous['video_time_s']])
    result = {'run': str(run), 'track_id': track_id, 'source_video':c['video'], 'range_s':[start,end],
              'track_observed_frames_in_range':len(target), 'review_video_frames':len(raw_frames),
              'region_matches_original_logs':all(r['logged_region']==r['replay_region'] for r in evidence if r['observed']),
              'replay_final_state_matches_run': snapshot == summary['final_state'],
              'pending_transitions':transitions,'max_inside_confirmation_elapsed_s':max((r['side_elapsed_s'] for r in evidence if r['replay_region']=='inside'),default=0),
              'geometry_only_inside_side_spans_s':spans,
              'geometry_only_max_inside_elapsed_s':max((b-a for a,b in spans),default=0),
              'parameters_changed':False,
              'source_config_sha256':hashlib.sha256((run/'config_used.json').read_bytes()).hexdigest(),
              'output_video_checks':{name:verify_output(out/name,width,height,fps,len(raw_frames)) for name in writers}}
    write_json(out/'state_replay.json',result)
    print(out)
    print(json.dumps({k:v for k,v in result.items() if k!='output_video_checks'},ensure_ascii=False,indent=2))
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--track',type=int,default=6)
    parser.add_argument('--start',type=float,default=6)
    parser.add_argument('--end',type=float,default=10)
    args=parser.parse_args()
    review(args.run,args.track,args.start,args.end)
