import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

root = Path('generated/youtube-7UXprjqSBvk-bgutil-probe')
frames = sorted((root/'frames').glob('*.jpg'))
segment = next((p for p in root.glob('segment.*') if p.suffix in {'.mp4','.webm','.mkv'} and p.stat().st_size > 100000), None)
result = {
    'status': 'segment_captured' if segment else 'failed',
    'video_id': '7UXprjqSBvk',
    'source_start_seconds': 1380,
    'source_end_seconds': 1440,
    'segment_file': segment.name if segment else None,
    'segment_bytes': segment.stat().st_size if segment else 0,
    'frame_count': len(frames),
}
if frames:
    thumb_w, thumb_h = 480, 270
    cols = 2
    rows = (len(frames)+cols-1)//cols
    sheet = Image.new('RGB',(thumb_w*cols,thumb_h*rows),'white')
    draw = ImageDraw.Draw(sheet)
    for i,path in enumerate(frames):
        im=Image.open(path).convert('RGB').resize((thumb_w,thumb_h))
        x=(i%cols)*thumb_w; y=(i//cols)*thumb_h
        sheet.paste(im,(x,y)); draw.text((x+8,y+8),path.stem,fill='white',stroke_width=2,stroke_fill='black')
    sheet.save(root/'contact-sheet.jpg','JPEG',quality=88,optimize=True)
(root/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

payload=io.BytesIO()
with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(root/'result.json','result.json')
    if (root/'ffprobe.json').exists(): zf.write(root/'ffprobe.json','ffprobe.json')
    if (root/'contact-sheet.jpg').exists(): zf.write(root/'contact-sheet.jpg','contact-sheet.jpg')
    for path in frames: zf.write(path,f'frames/{path.name}')
raw=payload.getvalue(); encoded=base64.b64encode(raw).decode('ascii')
chunk_size=6000
parts=[encoded[i:i+chunk_size] for i in range(0,len(encoded),chunk_size)]
for i,part in enumerate(parts):
    (root/'transfer'/f'part-{i:04d}.txt').write_text(part,encoding='ascii')
(root/'transfer-manifest.json').write_text(json.dumps({
    'zip_bytes':len(raw),'base64_chars':len(encoded),'chunk_size':chunk_size,
    'chunk_count':len(parts),'sha256':hashlib.sha256(raw).hexdigest(),
    'parts':[f'part-{i:04d}.txt' for i in range(len(parts))]
},indent=2),encoding='utf-8')
