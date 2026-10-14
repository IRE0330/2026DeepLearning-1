"""Inspect saved rule masks without altering user coordinates or model inputs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from cctv.config import load,resolve,validate
from cctv.geometry import in_polygon
from cctv.media import frame_at,image_write,unique_dir,write_json
from cctv.overlay import draw_zones


def inspect(run_path,previous_path):
    run,previous=resolve(run_path),resolve(previous_path)
    c,old=load(run/'config_used.json'),load(previous/'config_used.json')
    summary=load(run/'summary.json')
    w,h=summary['input_video']['width'],summary['input_video']['height']
    validate(c,video_size=(w,h))
    out=unique_dir('inspections','north_mask_review')
    rows=[json.loads(line) for line in (run/'diagnostics.jsonl').open(encoding='utf-8')]
    observations=[r for r in rows if r['kind'] in ('observation','excluded_observation')]
    def mask(polygons):
        m=np.zeros((h,w),np.uint8)
        for polygon in polygons:
            if polygon:
                p=np.array([[round(x*w),round(y*h)] for x,y in polygon],np.int32)
                cv2.fillPoly(m,[p],1)
        return m.astype(bool)
    waiting=mask([c['waiting_zone']])
    transit=mask([c['transit_zone']])
    excluded=mask(c['excluded_zones'])
    effective=waiting & ~transit & ~excluded
    actual=[]
    for r in observations:
        point=(r['point'][0]/w,r['point'][1]/h)
        inside_wait=in_polygon(point,c['waiting_zone'])
        inside_transit=in_polygon(point,c['transit_zone'])
        exclusions=[i+1 for i,poly in enumerate(c['excluded_zones']) if in_polygon(point,poly)]
        actual.append({'frame_index':r['frame_index'],'video_time_s':r['video_time_s'],'track_id':r['track_id'],
                       'point_x':r['point'][0],'point_y':r['point'][1],
                       'in_waiting_zone':inside_wait,'in_transit_zone':inside_transit,
                       'excluded_mask_indices':';'.join(map(str,exclusions)),
                       'eligible_waiting_point':inside_wait and not inside_transit and not exclusions,
                       'logged_waiting_state':r.get('waiting_state'), 'logged_kind':r['kind']})
    with (out/'observed_anchor_masks.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(actual[0]));writer.writeheader();writer.writerows(actual)
    write_json(out/'mask_check.json',{
        'run':str(run),'previous_run':str(previous),'changed_config_fields':[key for key in c if c[key]!=old.get(key)],
        'validation_passed':True,'side_confirm_s':c['rules']['side_confirm_s'],
        'mask_semantics':'rule exclusion by box bottom-center; original image still used by YOLO/ByteTrack',
        'mask_area_pixel_grid_estimates':{'waiting_pixels':int(waiting.sum()),
             'waiting_transit_overlap_pixels':int((waiting & transit).sum()),
             'waiting_excluded_overlap_pixels':int((waiting & excluded).sum()),
             'eligible_waiting_fraction':float(effective.sum()/waiting.sum())},
        'observation_frame_records_not_people_counts':{
            'all':len(actual),'inside_waiting':sum(r['in_waiting_zone'] for r in actual),
            'waiting_blocked_by_transit':sum(r['in_waiting_zone'] and r['in_transit_zone'] for r in actual),
            'waiting_blocked_by_exclusion':sum(r['in_waiting_zone'] and bool(r['excluded_mask_indices']) for r in actual),
            'excluded_points_all_zones':sum(bool(r['excluded_mask_indices']) for r in actual),
            'eligible_waiting_points':sum(bool(r['eligible_waiting_point']) for r in actual)},
        'summary':{key:summary[key] for key in ('processed_frames','status','elapsed_s','processing_fps','final_state')},
        'all_output_frames_decoded':summary['output_video']['all_frames_decoded'],
        'source_config_sha256':hashlib.sha256((run/'config_used.json').read_bytes()).hexdigest(),
        'current_config_equals_used':load('configs/north.json')==c,
        'coordinates_or_thresholds_modified_by_agent':False})
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
    for index in (0,120,171,216,239):
        frame,t=frame_at(c['video'],index/summary['input_video']['fps'])
        overlay=frame.copy()
        overlay[effective]=(40,170,40)
        overlay[waiting & transit]=(0,140,255)
        overlay[excluded]=(40,40,200)
        canvas=cv2.addWeighted(frame,.78,overlay,.22,0)
        draw_zones(canvas,c)
        selected=[r for r in observations if r['frame_index']==index]
        for r in selected:
            a=next(a for a in actual if a['frame_index']==index and a['track_id']==r['track_id'])
            color=(0,0,255) if a['excluded_mask_indices'] else (0,230,0) if a['eligible_waiting_point'] else (255,255,255)
            x,y=map(round,r['point'])
            cv2.circle(canvas,(x,y),5,color,-1)
            status='EXCLUDED' if a['excluded_mask_indices'] else 'WAIT '+str(a['logged_waiting_state']) if a['eligible_waiting_point'] else 'OUTSIDE WAIT'
            cv2.putText(canvas,f'{r["track_id"]} {status}',(x+5,y-5),cv2.FONT_HERSHEY_SIMPLEX,.4,color,1)
        im=Image.new('RGB',(w,h+96),'#111b26')
        im.paste(Image.fromarray(cv2.cvtColor(canvas,cv2.COLOR_BGR2RGB)),(0,96))
        draw=ImageDraw.Draw(im)
        draw.text((12,7),f'원본 {t:.3f}초: 현재 마스크와 관측 하단점',font=font,fill='white')
        draw.text((12,37),'초록: 대기 판정 가능한 영역/점 | 빨강: 제외 영역/점 | 흰 점: 대기 구역 밖',font=font,fill='white')
        draw.text((12,66),'영상의 픽셀을 지우는 마스크가 아닙니다. 초록 점도 대기 확정 여부를 별도로 확인해야 합니다.',font=font,fill='#cfdae6')
        im.save(out/f'masks_{index:06d}.png')
    # A reviewed, known poster detection in this north clip. Keep coordinates
    # unchanged and show why masking the drawn body does not mask its anchor.
    comparison=Image.new('RGB',(850,890),'#111b26')
    d=ImageDraw.Draw(comparison)
    d.text((12,8),'표지 그림 오탐: 하단점이 제외 마스크 아래에 남습니다',font=font,fill='white')
    d.text((12,43),'빨강: 저장된 제외 경계 / 노랑: ID 8 박스 / 흰 점: 제외되지 않은 하단점',font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18),fill='white')
    for j,index in enumerate((0,120)):
        frame,t=frame_at(c['video'],index/summary['input_video']['fps'])
        poly=np.array([[round(x*w),round(y*h)] for x,y in c['excluded_zones'][0]],np.int32)
        cv2.polylines(frame,[poly],True,(0,0,255),1)
        r=next(r for r in observations if r['frame_index']==index and r['track_id']==8)
        x1,y1,x2,y2=map(round,r['box'])
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,255),1)
        cv2.circle(frame,tuple(map(round,r['point'])),3,(255,255,255),-1)
        tile=cv2.resize(frame[80:350,320:455],(405,810),interpolation=cv2.INTER_NEAREST)
        comparison.paste(Image.fromarray(cv2.cvtColor(tile,cv2.COLOR_BGR2RGB)),(10+425*j,80))
        d.text((14+425*j,84),f'{t:.0f}초 / 하단 y={r["point"][1]:.1f}px',font=font,fill='#ffffff',stroke_width=1,stroke_fill='#000000')
    comparison.save(out/'poster_mask_miss.png')
    print(out)
    print((out/'mask_check.json').read_text(encoding='utf-8'))
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--previous',required=True)
    args=parser.parse_args()
    inspect(args.run,args.previous)
