"""Extract consecutive preview frames for a bounded visual inspection."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import av
import cv2
import numpy as np
from cctv.media import image_write

for name, run, source_start in [
    ('flow', 'micc_flow_sequence_20261014_113049_0ffa1ab3', 180),
    ('queue', 'micc_queue_sequence_20261014_113059_5f183758', 140),
    ('groups', 'micc_groups_sequence_20261014_113110_a4a811d4', 360)]:
    tiles = []
    with av.open(str(Path('outputs') / run / 'preview.mp4')) as container:
        for i, frame in enumerate(container.decode(video=0)):
            if i >= 12:
                break
            tile = cv2.resize(frame.to_ndarray(format='bgr24'), (320, 240))
            cv2.putText(tile, f'SOURCE FRAME {source_start+i}', (5, 55), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
            tiles.append(tile)
    image_write(Path('outputs') / run / 'consecutive_review.jpg', np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,12,4)]))
