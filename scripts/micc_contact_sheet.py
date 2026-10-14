"""Create labeled source-frame thumbnails for qualitative review, never labels."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from cctv.media import image_write
from cctv.micc import numeric_files

base = Path('data/micc/micc_crowd_counting')
for name in ('Flow', 'Queue', 'Groups'):
    files = numeric_files(base / name / 'RGB', '.png')
    selected = [files[i] for i in (0, len(files)//6, len(files)//3, len(files)//2, 2*len(files)//3, len(files)-1)]
    tiles = []
    for p in selected:
        frame = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
        frame = cv2.resize(frame, (640, 480))
        cv2.rectangle(frame, (0, 0), (640, 30), (0, 0, 0), -1)
        cv2.putText(frame, f'{name} source frame {p.stem} (FPS unknown)', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 1)
        tiles.append(frame)
    image_write(Path('inspections') / f'micc_{name.lower()}_source_contact.jpg', np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])]))
