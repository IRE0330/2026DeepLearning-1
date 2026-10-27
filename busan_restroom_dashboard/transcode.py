"""Generate a browser preview without changing the inference source."""
import sys
from fractions import Fraction
from pathlib import Path

def main(source,dest):
    import av
    tmp=Path(dest).with_suffix('.tmp.mp4')
    try:
        with av.open(source) as src, av.open(str(tmp),'w',options={'movflags':'+faststart'}) as dst:
            video=src.streams.video[0]
            fps=video.average_rate or Fraction(24,1)
            stream=dst.add_stream('libx264',rate=fps)
            stream.width=video.codec_context.width//2*2
            stream.height=video.codec_context.height//2*2
            stream.pix_fmt='yuv420p';stream.options={'crf':'22','preset':'fast'}
            first=None
            for i,frame in enumerate(src.decode(video=0)):
                # Preserve VFR timestamps if present; both previews and records use source time.
                stamp=frame.time
                if first is None:first=stamp or 0
                frame=frame.reformat(width=stream.width,height=stream.height,format='yuv420p')
                frame.time_base=Fraction(1,90000)
                frame.pts=round((stamp-first)*90000) if stamp is not None else round(i/float(fps)*90000)
                for packet in stream.encode(frame):dst.mux(packet)
            for packet in stream.encode():dst.mux(packet)
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True);raise
if __name__=='__main__':main(*sys.argv[1:])
