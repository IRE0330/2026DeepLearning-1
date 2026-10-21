"""Read saved observations; create a separate audit, never change inference or truth."""
import argparse
import collections
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cctv.core import Counter, Observation
from cctv.geometry import in_polygon, line_distance, segments_intersect

SOURCES = {
    'north': 'outputs/final/north',
    'south': 'outputs/final/south',
    'east': 'outputs/final/east',
}
MANUAL = {'east': (7, 6, 3), 'south': (4, 3, 3), 'north': (10, 11, 29)}


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def dump(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def table(p, rows, fields):
    with p.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def near(p, c):
    # Review selection only: fixed 0.08 normalized distance to the finite segment.
    a, b = c['boundary']
    vx, vy = b[0]-a[0], b[1]-a[1]
    u = max(0, min(1, ((p[0]-a[0])*vx+(p[1]-a[1])*vy)/(vx*vx+vy*vy)))
    return math.dist(p, (a[0]+u*vx, a[1]+u*vy)) <= .08


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=False)
    protected = set()
    for folder in ['configs', 'ground_truth', 'cctv-analysis', 'outputs', 'models']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and not any(x in p.parts for x in ['__pycache__', '.cache', 'build']):
                protected.add(p)
    for pattern in ['*.mp4', '*.mov', 'requirements*.txt', 'README.md', 'docs/*', 'cctv/*.py']:
        protected.update(p for p in ROOT.glob(pattern) if p.is_file())
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(protected)}
    dump(out/'preservation_before.json', before)
    git = {k: subprocess.check_output(['git', *cmd], cwd=ROOT).decode('utf-8').strip()
           for k, cmd in {'head':['rev-parse','HEAD'], 'branch':['branch','--show-current'],
                          'status_before':['status','--short']}.items()}
    dump(out/'git_baseline.json', git)
    inventory = []
    for p in sorted((ROOT/'outputs').rglob('summary.json')):
        s = read(p)
        v, final = s.get('input_video') or {}, s.get('final_state') or {}
        inventory.append(dict(run=str(p.parent.relative_to(ROOT)), status=s.get('status'),
                              restroom_id=s.get('restroom_id'), video_id=s.get('video_id'),
                              start_s=s.get('actual_start_s'), last_s=s.get('actual_last_frame_s'),
                              source_last_s=v.get('last_frame_time_s'), frames=s.get('processed_frames'),
                              entries=final.get('entries'), exits=final.get('exits'),
                              full_video=bool(s.get('actual_start_s') == 0 and v.get('last_frame_time_s') is not None
                                              and s.get('actual_last_frame_s') == v['last_frame_time_s']
                                              and s.get('processed_frames') == v.get('frame_count'))))
    dump(out/'run_inventory.json', inventory)
    identities, totals, candidates, timeline, replay_checks = {}, [], [], [], {}
    evidence_by_room = {}
    for room, rel in SOURCES.items():
        run = ROOT/rel
        s, c = read(run/'summary.json'), read(run/'config_used.json')
        v = s['input_video']
        video = ROOT/c['video']
        digest = sha(video)
        assert digest == s['source_video_sha256'] == c['video_sha256']
        assert s['video_id'] == c['video_id']
        assert s['status'] == 'completed' and s['actual_start_s'] == 0
        assert s['actual_last_frame_s'] == v['last_frame_time_s']
        assert s['processed_frames'] == v['frame_count']
        identities[room] = dict(video_filename=video.name, video_id=c['video_id'], sha256=digest,
                                duration_s=v['duration_s'], last_frame_s=v['last_frame_time_s'],
                                fps=v['fps'], frames=v['frame_count'], run=rel,
                                manual_source='사용자 전체 영상 수동 집계; 이벤트별 시각 미제공',
                                manual_identity_binding='현재 설정 원본에 대응시킴; 사용자 메시지에는 파일명/해시가 없어 독립적인 수동 집계 영상 해시 확인은 불가')
        manual_in, manual_out, initial = MANUAL[room]
        final = s['final_state']
        totals.append(dict(restroom_id=room, video_id=c['video_id'], manual_entries=manual_in,
                           manual_exits=manual_out, auto_entries=final['entries'], auto_exits=final['exits'],
                           entry_manual_minus_auto=manual_in-final['entries'], exit_manual_minus_auto=manual_out-final['exits'],
                           demo_initial_inside=initial, manual_final_checksum=initial+manual_in-manual_out,
                           automatic_final_inside=final['inside_estimate'], source='사용자 수동 집계',
                           event_times_available=False, is_event_ground_truth=False))
        with (run/'events.csv').open(encoding='utf-8-sig', newline='') as f:
            original_events = list(csv.DictReader(f))
        logs = [json.loads(l) for l in (run/'diagnostics.jsonl').read_text(encoding='utf-8').splitlines()]
        frames = collections.defaultdict(list)
        observations = collections.defaultdict(list)
        for n, r in enumerate(logs, 1):
            frames[r['frame_index']].append((n, r))
            if r['kind'] in ('observation', 'excluded_observation'):
                observations[r['track_id']].append(r)
        counter = Counter(c, v['width'], v['height'])
        states = []
        local = []

        def add(kind, t, tid, evidence, priority=3, frame=None, line=None):
            local.append(dict(restroom_id=room, video_id=c['video_id'], video_time_s=round(t, 6),
                              frame_index=frame if frame is not None else round(t*v['fps']), track_id=tid,
                              kind=kind, priority=priority, start_s=round(max(0, t-2), 3),
                              end_s=round(min(v['duration_s'], t+3), 3), evidence=evidence,
                              source=rel, diagnostic_line=line, is_confirmed_missed_event=False))

        for index, records in sorted(frames.items()):
            t = records[0][1]['video_time_s']
            obs = [Observation(r['track_id'], tuple(r['box']), r['confidence']) for _, r in records
                   if r['kind'] in ('observation', 'excluded_observation')]
            prior = {tid: copy.deepcopy(counter.tracks.get(tid)) for tid in set([o.track_id for o in obs]) | set(counter.tracks)}
            snapshot, events, replay_logs = counter.update(t, index, obs)
            for o in obs:
                a, b = prior.get(o.track_id), counter.tracks[o.track_id]
                p = counter.normalized(o.point)
                states.append(dict(restroom_id=room, video_time_s=t, frame_index=index, track_id=o.track_id,
                                   point_x=o.point[0], point_y=o.point[1], region=b.zone, origin=b.origin,
                                   side_elapsed_s=b.side_elapsed, side_confirm_s=c['rules']['side_confirm_s'],
                                   pending_destination=b.pending['destination'] if b.pending else '',
                                   boundary_distance=line_distance(p,c['boundary'])*counter.inside_sign,
                                   excluded=any(in_polygon(p, poly) for poly in c['excluded_zones'])))
                if a and a.point and a.last_t >= 0 and segments_intersect(counter.normalized(a.point), p, *c['boundary']):
                    d0, d1 = line_distance(counter.normalized(a.point),c['boundary']), line_distance(p,c['boundary'])
                    if d0*d1 <= 0 and abs(d1-d0)>1e-9 and a.origin is None:
                        add('geometric_crossing_without_confirmed_origin', t, o.track_id,
                            f'저장 관측 기준 유한 경계 교차; origin=None; previous_region={a.zone}; previous_side_elapsed={a.side_elapsed:.6f}s; gap={t-a.last_t:.6f}s; 실제 출입 미확인',1,index)
                if a and a.zone and a.side_elapsed < c['rules']['side_confirm_s'] and b.zone != a.zone and near(p,c):
                    add('side_confirmation_interrupted', t, o.track_id,
                        f'이전 영역={a.zone}; confirmation_elapsed={a.side_elapsed:.6f}s < required={c["rules"]["side_confirm_s"]}; next_region={b.zone}; origin={a.origin}',2,index)
            for line, r in records:
                kind, tid = r['kind'], r.get('track_id')
                a = prior.get(tid)
                evidence = json.dumps(r, ensure_ascii=False)
                if kind in ('finite_boundary_crossed_candidate','crossing_candidate_cancelled','opposite_region_without_confirmed_crossing','crossing_unconfirmed_after_gap'):
                    priority = 1 if kind == 'crossing_candidate_cancelled' or r.get('pending') else 2 if r.get('previous_origin') else 3
                    add(kind,t,tid,evidence,priority,index,line)
                if kind == 'tracker_id_not_observed' and a and a.pending:
                    add('observation_lost_after_crossing',t,tid,evidence+'; pending='+json.dumps(a.pending),1,index,line)
                if kind == 'first_observed':
                    found = next((o for o in obs if o.track_id == tid),None)
                    if found and near(counter.normalized(found.point),c):
                        add('new_id_near_entrance',t,tid,evidence+'; finite segment distance <= 0.08 normalized; possible ID split, not identity proof',2,index,line)
                if kind == 'excluded_observation':
                    prev = observations[tid]
                    preceding = next((z for z in reversed(prev) if z['frame_index'] < index),None)
                    if preceding is None or preceding['kind'] != 'excluded_observation' or index-preceding['frame_index']>1:
                        add('excluded_zone_episode',t,tid,evidence+'; 판정에서 제외; 출입 상태 초기화',1 if a and a.pending else 2,index,line)
            # Saved logs and replay must describe the exact same original event stream.
        assert len(counter.events) == len(original_events)
        assert all(str(e['direction']) == r['direction'] and e['track_id'] == int(r['track_id'])
                   and abs(e['video_time_s']-float(r['video_time_s'])) < 1e-8
                   for e,r in zip(counter.events,original_events))
        assert snapshot == s['final_state']
        replay_checks[room] = dict(events_match=True, final_state_match=True,
                                   frame_groups=len(frames), processed_frames=s['processed_frames'],
                                   diagnostic_kinds=dict(collections.Counter(r['kind'] for r in logs)))
        for tid, st in counter.tracks.items():
            if st.pending:
                add('pending_at_end',s['actual_last_frame_s'],tid,json.dumps(st.pending),1)
        for r in local:
            t, tid = r['video_time_s'], r['track_id']
            nearby = [e for e in original_events if int(e['track_id'])==tid and -1e-6 <= float(e['video_time_s'])-t <= 5]
            r['same_id_confirmation_within_5s'] = '; '.join(f'{e["direction"]}@{float(e["video_time_s"]):.6f}' for e in nearby)
        candidates.extend(local)
        timeline.extend(dict(r, row_type='review_candidate') for r in local)
        for e in original_events:
            timeline.append(dict(restroom_id=room,video_id=c['video_id'],video_time_s=float(e['video_time_s']),
                                 frame_index=int(e['frame_index']),track_id=int(e['track_id']),kind='automatic_'+e['direction'],
                                 row_type='confirmed_automatic',evidence=json.dumps(e,ensure_ascii=False),source=rel))
        evidence_by_room[room] = (c,v,observations,states)
        (out/room).mkdir()
        table(out/room/'track_states.csv',states,list(states[0]))
        # Preserve original template schema in a fresh editing area, without inventing labels.
        truth=out/'truth_to_fill'/room
        truth.mkdir(parents=True)
        for name in ['events.csv','waiting.csv','inside.csv','metadata.json']:
            (truth/name).write_bytes((ROOT/'ground_truth'/room/name).read_bytes())
        meta=read(truth/'metadata.json')
        meta.update(video_id=c['video_id'],video_sha256=digest,video_filename=video.name,
                    event_time_policy='manual_destination_side_confirmation_0.2s',events_complete=False,
                    note='시각별 수동 정답 미작성. 전체 구간 확인 전 events_complete를 true로 바꾸지 마세요.')
        dump(truth/'metadata.json',meta)
    dump(out/'baseline_manifest.json',dict(version='manual-total-baseline-v1',git=git,sources=identities,
         selection='Latest single full-video saved run per environment; partial/aborted/package smoke runs excluded',
         manual_video_binding_caveat='User supplied environment names and full totals, not file hashes; current registered originals used, never obsolete north video',
         thresholds_changed=False,automatic_events_modified=False))
    dump(out/'manual_totals.json',dict(source='사용자 수동 집계',event_times_available=False,totals=totals,
         interpretation='총합 차이는 순차이이며 누락 이벤트 수/Recall/F1이 아님. 수동 최종 내부는 시연 초기값 검산값.'))
    table(out/'totals_comparison.csv',totals,list(totals[0]))
    candidates.sort(key=lambda r:(r['restroom_id'],r['video_time_s'],r['track_id'],r['kind']))
    for i,r in enumerate(candidates,1):
        r['candidate_id']=f'C{i:04d}'
    table(out/'review_candidates.csv',candidates,list(candidates[0]))
    fields=sorted(set().union(*(r.keys() for r in timeline)))
    table(out/'chronological_events_and_candidates.csv',sorted(timeline,key=lambda r:(r['restroom_id'],r['video_time_s'])),fields)
    dump(out/'replay_checks.json',replay_checks)
    table(out/'manual_event_worksheet.csv',[],['restroom_id','video_id','person_label','direction','crossing_time_s',
          'destination_stable_start_s','confirmation_time_s','uncertain','notes'])
    # Select candidate episodes; overlapping reasons remain in CSV, images use representative windows.
    priority=[]
    for room in SOURCES:
        local=[r for r in candidates if r['restroom_id']==room]
        chosen=[]
        for r in sorted(local,key=lambda r:(r['priority'],bool(r['same_id_confirmation_within_5s']),r['video_time_s'])):
            if any(abs(r['video_time_s']-z['video_time_s'])<2 for z in chosen):continue
            chosen.append(r)
            if len(chosen)>= (10 if room=='north' else 5):break
        priority.extend(chosen)
    self_images(out,priority,evidence_by_room)
    table(out/'priority_windows.csv',priority,list(priority[0]))
    after={rel:sha(ROOT/rel) for rel in before}
    changed=[rel for rel in before if before[rel]!=after[rel]]
    dump(out/'preservation_check.json',dict(protected_files=len(before),changed=changed,all_unchanged=not changed,
         policy='SHA-256 of all preexisting output files, original videos, models, configs, truth, package including dist/lock/source; no installation or inference',
         git_push=False))
    assert not changed
    finalize(out)
    print(json.dumps(dict(output=str(out),candidates=len(candidates),priority=[{k:r[k] for k in ['restroom_id','video_time_s','track_id','kind']} for r in priority],preserved=len(before)),ensure_ascii=False))


def self_images(out, priority, evidence):
    import av
    import cv2
    import numpy as np
    from cctv.overlay import draw_zones
    from cctv.media import image_write
    for room,(c,v,tracks,states) in evidence.items():
        selected=[r for r in priority if r['restroom_id']==room]
        requested={}
        for n,r in enumerate(selected,1):
            r['image_prefix']=r.get('image_prefix',f'{room}/review_{n:02d}')
            center=r['video_time_s']
            requested[n]=[max(0,min(v['frame_count']-1,round(t*v['fps']))) for t in [center-1,center,center+.5,center+1.5]]
        targets={i for indices in requested.values() for i in indices}
        frames={}
        with av.open(str(ROOT/c['video'])) as container:
            for i,decoded in enumerate(container.decode(video=0)):
                if i in targets: frames[i]=decoded.to_ndarray(format='bgr24')
                if len(frames)==len(targets):break
        for n,r in enumerate(selected,1):
            rawtiles,overlays=[],[]
            tid=r['track_id']
            path=[z for z in tracks[tid] if r['start_s']<=z['video_time_s']<=r['end_s']]
            for i in requested[n]:
                raw=frames[i].copy()
                overlay=draw_zones(raw.copy(),c)
                previous=None
                for z in path:
                    if z['frame_index']>i:break
                    pt=tuple(round(x) for x in z['point'])
                    if previous and z['frame_index']==previous['frame_index']+1:
                        cv2.line(overlay,tuple(round(x) for x in previous['point']),pt,(255,255,0),2)
                    cv2.circle(overlay,pt,3,(0,0,255) if z['kind']=='excluded_observation' else (0,255,255),-1)
                    previous=z
                z=next((z for z in tracks[tid] if z['frame_index']==i),None)
                if z:
                    x1,y1,x2,y2=map(round,z['box'])
                    cv2.rectangle(overlay,(x1,y1),(x2,y2),(0,255,255),2)
                label=f'{room} {i/v["fps"]:.3f}s ID {tid} '+('observed' if z else 'NOT OBSERVED')
                for img,collection in [(raw,rawtiles),(overlay,overlays)]:
                    tile=cv2.resize(img,(640,360))
                    tile=cv2.copyMakeBorder(tile,30,0,0,0,cv2.BORDER_CONSTANT)
                    cv2.putText(tile,label,(8,21),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                    collection.append(tile)
            for suffix,tiles in [('source',rawtiles),('trajectory',overlays)]:
                image_write(out/(r['image_prefix']+'_'+suffix+'.jpg'),np.vstack([np.hstack(tiles[:2]),np.hstack(tiles[2:])]))
    for r in priority:
        assert (out/(r['image_prefix']+'_source.jpg')).exists()


def finalize(out):
    """Add readable interpretation; retain raw records and all original run files."""
    replacements = {'保存観測の有限境界交差':'저장 관측 기준 유한 경계 교차',
                    '実出入未確認':'실제 출입 미확인', '前領域':'이전 영역',
                    '判定から除外・出入状態を初期化':'판정에서 제외; 출입 상태 초기화'}
    for name in ['review_candidates.csv','chronological_events_and_candidates.csv','priority_windows.csv']:
        p=out/name
        content=p.read_text(encoding='utf-8-sig')
        for old,new in replacements.items(): content=content.replace(old,new)
        p.write_text(content,encoding='utf-8-sig',newline='')
    with (out/'review_candidates.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    extras=[]
    for tid,kind,t in [(191,'excluded_zone_episode',68.583333),(157,'crossing_unconfirmed_after_gap',56.791667),
                       (194,'crossing_unconfirmed_after_gap',70.375)]:
        r=next(r for r in rows if r['restroom_id']=='north' and int(r['track_id'])==tid and r['kind']==kind and abs(float(r['video_time_s'])-t)<.001)
        r=dict(r)
        for k in ['video_time_s','start_s','end_s']:r[k]=float(r[k])
        r['track_id']=int(r['track_id'])
        r['image_prefix']=f'north/extra_{len(extras)+1:02d}'
        extras.append(r)
    run=ROOT/SOURCES['north']
    logs=[json.loads(l) for l in (run/'diagnostics.jsonl').read_text(encoding='utf-8').splitlines()]
    tracks=collections.defaultdict(list)
    for r in logs:
        if r['kind'] in ['observation','excluded_observation']:tracks[r['track_id']].append(r)
    self_images(out,extras,{'north':(read(run/'config_used.json'),read(run/'summary.json')['input_video'],tracks,[])})
    if not (out/'extra_windows.csv').exists(): table(out/'extra_windows.csv',extras,list(extras[0]))
    totals=read(out/'manual_totals.json')['totals']
    sources=read(out/'baseline_manifest.json')['sources']
    checks=read(out/'preservation_check.json')
    text=['# 수동 총합 비교 및 이벤트 검토 — 2026-10-18',
          '', '이번 작업은 기준 결과 동결·사용자 수동 총합 저장·실패 가능성 검토 자료 준비까지입니다. 자동 이벤트·CSV·마스킹·임계값·모델·Streamlit 인터페이스·패키지를 수정하지 않았습니다. 재추론·학습·앙상블·Git push는 없습니다.',
          '', '## 비교 기준과 영상 식별', '',
          '시작 Git은 `ef16110a6ae176761fb60294173659d26255b646`, 브랜치는 `mvp/busan-cctv-20261014`이며 최초 작업 전 상태는 clean이었습니다. `git_baseline.json`의 status_before는 자료 폴더 생성 후 캡처되어 이번 새 파일만 표시합니다. README·루트/패키지 HANDOFF와 최신 전체 실행을 확인했습니다.',
          '', '| 환경 | 원본 파일 | 영상 ID | 길이 / FPS / 프레임 |', '|---|---|---|---|']
    for room in ['east','south','north']:
        s=sources[room]
        text.append(f'| {room} | {s["video_filename"]} | `{s["video_id"]}` | {s["duration_s"]:.6f}초 / {s["fps"]:g} / {s["frames"]} |')
    text.extend(['', '원본 SHA-256을 다시 계산해 해당 전체 실행의 source_video_sha256·config_used의 video_sha256과 일치함을 확인했습니다. 시작 0초부터 마지막 프레임까지 처리됐고 프레임 수도 원본 전체와 같습니다. 최신 단일 전체 실행을 기준 버전 `manual-total-baseline-v1`로 고정했습니다. 전체 경로·해시·시각은 [baseline_manifest.json](baseline_manifest.json), 전체/부분 시험 구분은 [run_inventory.json](run_inventory.json)에 있습니다.',
                 '', '사용자는 환경명과 전체 총합을 제공했으며 파일명/해시를 직접 제공하지 않았습니다. 위 현재 등록 원본에 대응시켜 기록했으며 사용자가 본 파일의 해시 자체를 독립 확인한 것은 아닙니다. 옛 북쪽_최종.mp4(약94초), 동시 입력 중단 결과, 패키지의 1~3초 호출 시험은 비교에서 제외했습니다.',
                 '', '## 수동 총합과 자동 총합', '', '| 환경 | 수동 입장/퇴장 | 자동 입장/퇴장 | 수동−자동 입장/퇴장 | 시연 초기값 | 수동 최종 검산 | 자동 최종 내부 |', '|---|---:|---:|---:|---:|---:|---:|'])
    for r in totals:
        text.append(f'| {r["restroom_id"]} | {r["manual_entries"]}/{r["manual_exits"]} | {r["auto_entries"]}/{r["auto_exits"]} | +{r["entry_manual_minus_auto"]}/+{r["exit_manual_minus_auto"]} | {r["demo_initial_inside"]} | {r["manual_final_checksum"]} | {r["automatic_final_inside"]} |')
    text.extend(['', '출처는 사용자 수동 집계이며 이벤트별 시각은 아직 없습니다. `manual_totals.json`과 `totals_comparison.csv`는 이벤트 정답과 분리했습니다. 수동 최종은 east 3+7−6=4, south 3+4−3=4, north 29+10−11=28의 검산값이며 실제 내부 관측 정답이 아닙니다. 자동 내부 5/3/25와 기존 CSV는 유지했습니다.',
                 '', '**총합 차이는 누락 이벤트 개수나 Recall/F1이 아닙니다.** 오탐과 누락이 상쇄될 수 있어 시각별 1:1 대응 없이 TP/FP/FN을 알 수 없습니다. 성능 평가는 실행하지 않았습니다.',
                 '', '## 검토 자료 읽기', '',
                 '- [시간순 자동 이벤트와 후보](chronological_events_and_candidates.csv): 환경별 영상 시각순; confirmed_automatic은 기존 자동 확정이고 review_candidate는 검토 표시입니다.',
                 '- [후보 상세](review_candidates.csv): 환경·영상 ID·시각·프레임·추적 ID·근거·원본 로그 줄 번호·구간·후속 확정 여부. 합계 301행은 중복 이유/재통과를 포함하며 사람 수가 아닙니다.',
                 '- [대표 장면 목록](priority_windows.csv)과 [마스킹/짧은 공백 추가 장면](extra_windows.csv): image_prefix에 `_source.jpg` 또는 `_trajectory.jpg`를 붙이면 대응 이미지입니다. 총 23개 장면, 원본/궤적 46장입니다.',
                 '- 각 환경 `track_states.csv`: 저장 관측의 발 기준점(검출 박스 하단 중앙), origin, 영역, 확인 누적시간, 미확정 목적지, 경계 거리, 제외 여부입니다.',
                 '', '궤적은 해당 ID의 연속 프레임끼리만 연결했습니다. 노란 점은 관측 기준점, 빨간 점은 제외 관측, 청록 궤적은 시간순 이동입니다. NOT OBSERVED는 그 프레임에 해당 ID가 없다는 뜻입니다. 다른 ID가 같은 사람인지 자동으로 합치지 않았습니다. 원본 영상은 별도 플레이어에서 이어서 보세요. 4장짜리 이미지로 전체 행동을 확정하지 않습니다.',
                 '', '| 표식 | 의미 |', '|---|---|',
                 '| observation_lost_after_crossing | 유한 경계 통과 후보가 남은 상태에서 ID 관측 유실 |',
                 '| geometric_crossing_without_confirmed_origin | 저장 기준점이 유한 경계를 넘지만 출발 영역 origin이 아직 없음 |',
                 '| side_confirmation_interrupted | 내부/외부 확인 누적이 0.2초에 못 미친 채 영역이 바뀌거나 제외됨 |',
                 '| crossing_unconfirmed_after_gap | 짧은 공백 뒤 재관측되어 출입 상태 초기화; pending이 없어도 발생 |',
                 '| crossing_candidate_cancelled | 경계 재통과/원래 영역 재확인 등으로 후보 취소; 근거에 reason 기록 |',
                 '| new_id_near_entrance | 출입선 유한 선분에서 정규화 거리 0.08 이내 새 ID; 검토 선택용 거리이며 판정값 변경 아님 |',
                 '| excluded_zone_episode | 기준점이 제외 구역에 들어가 출입 판정/상태에서 빠진 관측 묶음 |',
                 '| pending_at_end | 영상 종료 시 상태에 남아 있는 오래된 후보일 수도 있음; 발생 시각은 evidence의 crossing_time_estimate_s 확인 |',
                 '', '## 북쪽 우선 확인 순서', '', '| 순서 | 원본 구간 | ID / 근거 | 자료 |', '|---|---|---|---|',
                 '| 1 | 00:00~00:09 | ID12: 0.833초 교차 시 origin 없음. ID23: 5.083초 새 ID, 5.125/5.333초 교차; 내부 관측 0.125초 후 되넘음. ID27은 7.125초 새 관측. 같은 사람이 이어지는지 확인 | [0.833초](north/review_01_trajectory.jpg), [5.125초](north/review_02_trajectory.jpg), [7.125초](north/review_06_trajectory.jpg) |',
                 '| 2 | 01:26~01:33 | ID198: 88.875~90.292초 사이 여러 번 경계 교차, origin 없음, 같은 ID 자동 확정 없음. 발점 흔들림/출입 방향/전체 이동 확인 | [원본](north/review_03_source.jpg), [궤적](north/review_03_trajectory.jpg) |',
                 '| 3 | 01:06~01:13 | ID191: 68.583/68.833/69.208초 제외 관측. ID194: 70.375초 재관측 gap=0.083333초로 origin 초기화. 이웃 ID4 자동 입장과 다른 실제 사람이 있는지 확인 | [제외 구역](north/extra_01_trajectory.jpg), [짧은 공백](north/extra_03_trajectory.jpg) |',
                 '| 4 | 00:54~01:00 | ID157: 56.792초 gap=0.166667초로 이전 outside 초기화. 자동 퇴장 이력과 ID168 새 관측을 전후 비교 | [공백](north/extra_02_trajectory.jpg) |',
                 '| 5 | 00:26~00:32, 01:41~01:45.167 | ID3 28.333초/ID249 103.167초 재통과 취소. 각각 28.875초 entry/103.750초 exit로 후속 확정됨. 취소 자체를 누락으로 세지 않기 위한 확인 | [ID3](north/review_04_trajectory.jpg), [ID249](north/review_05_trajectory.jpg) |',
                 '', '위 순서는 이상 징후와 직접 근거를 바탕으로 정한 검토 순서이며 총합 차이가 실제로 발생한 구간을 확정한 순위가 아닙니다. 북쪽 46회의 공백 초기화 중 일부는 max_observation_gap_s=0.25초보다 짧아도 발생합니다. 코드가 직전 missing=True인 경우에도 초기화하기 때문입니다. 값을 바꾸지 않았습니다.',
                 '', '남쪽은 **28~34초**(ID31 후보 취소), **47~53초**(ID47: 49.282초 교차 후보 뒤 49.333초 관측 유실), **83~90초**(ID90/96 출발 확인 없는 교차)를 먼저 보세요. 종료 pending_at_end의 시각 94.2초는 종료 상태를 기록한 시점이고 새 출입 시점이 아닙니다. ID47의 오래된 49.282초 후보가 남은 것입니다.',
                 '', '동쪽은 **17~25초**(ID44 19.933초 관측 유실, ID109 취소, ID115/121 교차), **53~62초**(ID297/317 확인 없는 교차), **62~68초**(ID329 취소), **74~80초**(ID387 교차)를 검토하세요. 같은 사람의 ID 분리인지, 제외 구역으로 빠졌는지, 실제 출입인지 구분해야 합니다.',
                 '', '**자동 후보는 실제 누락이라고 단정할 수 없습니다. 후보가 전혀 생성되지 않은 실제 출입도 있을 수 있으므로 세 영상 전체를 처음부터 끝까지 수동 이벤트로 작성해야 합니다.**',
                 '', '## 정답 입력 방법과 시각 기준', '',
                 '기존 양식은 저장소 `ground_truth/{north,south,east}/events.csv`이고 3열 `restroom_id,video_time_s,direction`입니다. 기존 파일은 보존했습니다. 이번 작업용 [truth_to_fill](truth_to_fill/)에 같은 양식의 빈 사본과 영상 식별 metadata를 준비했으므로 여기에 입력하세요. 패키지 안의 여러 사본과 섞지 말고 이 폴더 하나를 정답 편집본으로 사용하세요.',
                 '', '1. 원본의 0초를 기준으로 입력합니다. 01:28.5는 88.5초입니다. KST 촬영시각/CSV 구간 종료시각을 쓰지 않습니다. entry=외부→내부, exit=내부→외부이며 한 실제 출입마다 한 행을 씁니다. 자동 track_id는 사람 정답 ID가 아닙니다.',
                 '2. [manual_event_worksheet.csv](manual_event_worksheet.csv)에 먼저 실제 사람용 person_label, direction, crossing_time_s, destination_stable_start_s, confirmation_time_s를 적습니다. crossing_time_s는 발 하단 중앙이 설정된 **유한 출입선**을 넘는 대략 시각입니다. 되돌아감·가림·관측 불확실은 uncertain/notes에 적고 자동 결과를 복사하지 않습니다.',
                 '3. **이번 정답의 events.csv video_time_s는 사람이 확인한 목적지 영역 판정 확정 시각으로 통일합니다.** 출발 영역 확인 후 경계를 넘어 목적지 내부/외부 영역에서 발 기준점이 연속 0.2초 유지된 첫 프레임 시각을 씁니다. 첫 목적지 프레임에서 누적은 0초이며, 그 시각+0.2초 이상인 첫 실제 프레임이 기준입니다. 경계 근처 margin·확인 영역은 기존 config_used와 궤적 그림을 참고하세요. 목적지 연속 확인이 끊기면 유지 시작을 다시 잡습니다. 자동 ID가 끊겨도 영상으로 같은 사람임을 확인할 수 있으면 사람의 연속 행동을 기준으로 작성합니다.',
                 '4. crossing_time_s는 참고용이며 evaluate 입력으로 쓰지 않습니다. crossing+0.2초를 일괄 계산하거나 자동 판정 시각을 그대로 베끼지 마세요. 목적지 영역 도달이 늦을 수 있습니다. 시각/방향이 확인되지 않으면 worksheet에 남기고 events.csv에 추측 시각을 넣지 않습니다. 미해결 사건이 있으면 events_complete=false를 유지합니다.',
                 '5. events.csv에 worksheet의 restroom_id, confirmation_time_s, direction만 옮깁니다. 예컨대 사람이 확인한 목적지 안정 시작이 12.000초이고 30FPS에서 12.200초까지 연속 유지됐다면 video_time_s=12.2입니다. 이는 작성 방법의 가상 예시이며 정답 파일에는 넣지 않았습니다. CSV 헤더 다음부터 실제 확인한 행만 쓰고 불필요한 빈 행/총합 행은 넣지 않습니다.',
                 '6. 환경별 전체 영상의 모든 출입을 작성한 뒤 수동 총합 east 7/6, south 4/3, north 10/11과 검산합니다. 다르면 영상을 다시 확인하고 임의 행을 추가하지 않습니다. 완료 후 metadata.is_example=false, events_complete=true, annotated_start_s=0, annotated_end_s=마지막 프레임 시각(east 89.966666667, south 94.2, north 105.125)로 설정합니다. 영상 길이와 마지막 프레임 시각은 다릅니다. 검산 내부 인원을 inside.csv에 넣지 말고 실제 내부 관측 정답이 없으면 비워둡니다.',
                 '', '현재 evaluate.py는 자동 `events.csv.video_time_s`(판정 확정 시각)와 정답 video_time_s를 같은 방향끼리 기본 ±1초, 1:1로 매칭합니다. `crossing_time_estimate_s`는 매칭에 사용하지 않습니다. 기존 PACED_INPUT의 경계 통과 시각 권고와 혼용하지 않고 이번 정답은 위 확정 시각 기준을 사용합니다. 물리적 경계 통과 시각 평가가 필요해지면 별도 정책·평가 버전으로 다뤄야 합니다.',
                 '', '정답 전체 작성과 metadata 확인이 끝난 뒤에만 아래 명령을 실행합니다(이번에는 실행하지 않았습니다).', '', '```powershell'])
    for room in ['north','south','east']:
        text.append(f'& .\\.venv\\Scripts\\python.exe -B -m cctv evaluate --run "{SOURCES[room]}" --truth "{out.relative_to(ROOT).as_posix()}/truth_to_fill/{room}" --tolerance 1.0')
    text.extend(['```', '', '평가기는 현재 영상 ID/해시를 강제 검사하지 않으므로 실행 전 baseline_manifest와 정답 metadata의 video_id/video_sha256을 직접 대조하세요. 일부 구간만 라벨링했다면 해당 구간만 평가해야 하며 전체 총합과 비교해서는 안 됩니다.',
                 '', '## 검증 및 보존', '',
                 f'저장 관측 {2524+2827+2700:,}개 프레임을 기존 Counter로 재생했고 기존 이벤트 26건의 시각·방향·ID 및 세 환경 최종 상태가 일치했습니다. [replay_checks.json](replay_checks.json)에 근거가 있습니다. [preservation_check.json](preservation_check.json)의 기존 {checks["protected_files"]}개 파일 SHA-256이 모두 유지됐습니다. 원본 영상·모델·모든 기존 outputs·설정/마스크·정답·분석 패키지 소스/배포본/잠금 파일을 포함합니다. 패키지 설치나 빌드는 수행하지 않았습니다.',
                 '', 'CSV 13열, demo 1초 기록, 한국시간 정시 1시간 분할, 운영 10초 기본값과 Streamlit 인터페이스는 그대로입니다. 자동 출입 이벤트 추가·CSV 보정·임계값 변경·Random Forest/앙상블/모델 학습은 없습니다.'])
    (out/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
