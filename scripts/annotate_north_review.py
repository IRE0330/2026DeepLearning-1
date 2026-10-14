"""Readable Korean evidence panels for the reviewed north ID 6 case."""
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from cctv.media import frame_at,image_write

out=Path(sys.argv[1])
c=json.loads((out/'config_used.json').read_text(encoding='utf-8'))
rows=list(csv.DictReader((out/'track_state.csv').open(encoding='utf-8-sig')))
rows={int(r['frame_index']):r for r in rows}
metadata=json.loads((out/'state_replay.json').read_text(encoding='utf-8'))
run=Path(metadata['run'])
fps=json.loads((run/'summary.json').read_text(encoding='utf-8'))['input_video']['fps']
logs=[json.loads(line) for line in (run/'diagnostics.jsonl').open(encoding='utf-8')]
obs={r['frame_index']:r for r in logs if r.get('track_id')==6 and r['kind']=='observation'}
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
bold=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',26)
crop=(180,70,425,345)

def panel(index,zones=True,box=True):
    frame,t=frame_at(c['video'],index/fps)
    if zones:
        for key,color in [('inside_zone',(255,50,210)),('outside_zone',(230,190,0))]:
            p=np.array([[round(x*1280),round(y*720)] for x,y in c[key]],np.int32)
            overlay=frame.copy()
            cv2.fillPoly(overlay,[p],color)
            frame=cv2.addWeighted(frame,.87,overlay,.13,0)
            cv2.polylines(frame,[p],True,color,1)
        a,b=[(round(x*1280),round(y*720)) for x,y in c['boundary']]
        cv2.line(frame,a,b,(0,230,0),2)
    if box and index in obs:
        r=obs[index]
        x1,y1,x2,y2=map(round,r['box'])
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,255),1)
        cv2.circle(frame,tuple(map(round,r['point'])),3,(0,0,255),-1)
    x1,y1,x2,y2=crop
    return cv2.resize(frame[y1:y2,x1:x2],(490,550),interpolation=cv2.INTER_NEAREST)

def canvas(title,note,left,right,left_caption,right_caption,name):
    im=Image.new('RGB',(1020,700),'#101823')
    im.paste(Image.fromarray(cv2.cvtColor(left,cv2.COLOR_BGR2RGB)),(10,94))
    im.paste(Image.fromarray(cv2.cvtColor(right,cv2.COLOR_BGR2RGB)),(520,94))
    d=ImageDraw.Draw(im)
    d.text((15,10),title,font=bold,fill='white')
    d.text((15,49),note,font=small,fill='#d3dce6')
    d.text((15,652),left_caption,font=small,fill='white')
    d.text((525,652),right_caption,font=small,fill='white')
    im.save(out/name)

canvas('7초 후보: 실제 발 이동과 박스 하단 변화는 다릅니다',
       '노란 테두리=추적 박스 / 빨간 점=박스 하단 중앙 / 초록=경계 / 보라=내부 / 청록=외부',
       panel(169),panel(171),'7.042초: 하단 y=262.8px','7.125초: 하단 y=235.0px (다리 가림)', 'anchor_jump_compare.png')
canvas('8초 후반: 동일 ID가 다른 인물로 이어지는 사례',
       'ID 6을 같은 이용자의 왕복 경로로 해석하면 안 됩니다. 좌표·판정 시간을 변경하지 않았습니다.',
       panel(204,False),panel(216,False),'8.500초: 밝은 상의·청바지 인물','9.000초: 노란 옷 인물에 ID 6 박스', 'id_association_compare.png')

base=panel(171,True,False)
im=Image.new('RGB',(1020,770),'#101823')
im.paste(Image.fromarray(cv2.cvtColor(base,cv2.COLOR_BGR2RGB)),(10,100))
d=ImageDraw.Draw(im)
d.text((15,12),'현재 구역과 ID 6의 박스 하단 궤적 (6~10초)',font=bold,fill='white')
d.text((15,55),'구역 좌표는 저장된 설정 그대로입니다. 궤적은 실제 발 위치나 동일인 정답이 아닙니다.',font=small,fill='#d3dce6')
def xy(index):
    r=rows[index]
    return (10+2*(float(r['point_x'])-crop[0]),100+2*(float(r['point_y'])-crop[1]))
segments=[(144,169,'#35c6ff','6.000~7.042초'),(170,185,'#ffc14a','7.083~7.708초'),
          (186,203,'#e0e5eb','7.750~8.458초'),(204,239,'#ff71bd','8.500~9.958초: 대상 변경 구간 포함')]
for a,b,color,label in segments:
    pts=[xy(i) for i in range(a,b+1) if i in rows and rows[i]['observed']=='True']
    d.line(pts,fill=color,width=2)
    for p in pts:
        d.ellipse((p[0]-2,p[1]-2,p[0]+2,p[1]+2),fill=color)
for index,text,loc in [(169,'7.042',(525,315)),(171,'7.125',(525,205)),(186,'7.750 해제',(525,365)),(216,'9.000 다른 인물',(525,445))]:
    p=xy(index)
    d.line([p,(loc[0]-10,loc[1]+12)],fill='white',width=1)
    d.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),outline='white',width=2)
    d.text(loc,text,font=font,fill='white')
for j,(_,_,color,label) in enumerate(segments):
    d.text((530,530+32*j),label,font=small,fill=color)
d.text((15,675),'초록: 현재 출입 경계 / 보라: 내부 확인 구역 / 청록: 외부 확인 구역',font=font,fill='white')
d.text((15,711),'7.75초는 실제 퇴장 확정이 아니라 박스 하단의 경계 역방향 이동입니다.',font=small,fill='#d3dce6')
im.save(out/'zones_trajectory_korean.png')
print(out/'zones_trajectory_korean.png')
