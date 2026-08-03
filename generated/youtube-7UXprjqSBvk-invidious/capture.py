import base64
import hashlib
import io
import json
import math
import subprocess
import time
import urllib.parse
import zipfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageStat

root = Path('generated/youtube-7UXprjqSBvk-invidious')
frames_dir = root / 'frames'
sb_dir = root / 'storyboard-frames'
video_id = '7UXprjqSBvk'
start_s, end_s = 1380, 1500
instances = [
    'https://inv.nadeko.net',
    'https://invidious.nerdvpn.de',
    'https://yt.chocolatemoo53.com',
    'https://invidious.tiekoetter.com',
    'https://invidious.f5.si',
    'https://inv.zoomerville.com',
    'https://inv.thepixora.com',
    'https://inv1.nadeko.net',
    'https://inv2.nadeko.net',
    'https://inv3.nadeko.net',
    'https://inv4.nadeko.net',
    'https://inv5.nadeko.net',
    'https://invidious.adminforge.de',
    'https://invidious.private.coffee',
    'https://invidious.privacyredirect.com',
    'https://inv.us.projectsegfau.lt',
    'https://inv.bp.projectsegfau.lt',
    'https://invidious.projectsegfau.lt',
    'https://invidious.drgns.space',
    'https://invidious.einfachzocken.eu',
    'https://invidious.jing.rocks',
    'https://invidious.0011.lt',
    'https://iv.ggtyler.dev',
    'https://nyc1.iv.ggtyler.dev',
    'https://cal1.iv.ggtyler.dev',
    'https://invidious.lunar.icu',
    'https://iv.duti.dev',
    'https://invid-api.poketube.fun',
]
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/150 Safari/537.36',
    'Accept': 'application/json,text/plain,*/*',
})
attempts = []
metadata = None
selected_instance = None

for instance in instances:
    url = f'{instance}/api/v1/videos/{video_id}?local=true'
    entry = {'instance': instance, 'url': url}
    try:
        response = session.get(url, timeout=24, allow_redirects=True)
        entry.update({'http_status': response.status_code, 'content_type': response.headers.get('content-type'), 'bytes': len(response.content)})
        if response.status_code == 200 and 'json' in (response.headers.get('content-type') or '').lower():
            data = response.json()
            entry.update({
                'status': 'api_success',
                'title': data.get('title'),
                'lengthSeconds': data.get('lengthSeconds'),
                'formatStreams': len(data.get('formatStreams') or []),
                'adaptiveFormats': len(data.get('adaptiveFormats') or []),
                'storyboards': len(data.get('storyboards') or []),
            })
            if data.get('videoId') == video_id or data.get('title'):
                metadata = data
                selected_instance = instance
                attempts.append(entry)
                break
        else:
            entry['status'] = 'api_failed'
            entry['body_prefix'] = response.text[:500]
    except Exception as exc:
        entry.update({'status': 'exception', 'error': repr(exc)})
    attempts.append(entry)

(root / 'instance-attempts.json').write_text(json.dumps(attempts, ensure_ascii=False, indent=2), encoding='utf-8')
if metadata:
    sanitized = dict(metadata)
    # Keep metadata but redact expiring media URLs from the committed file.
    for key in ('formatStreams','adaptiveFormats'):
        redacted=[]
        for fmt in metadata.get(key) or []:
            item={k:v for k,v in fmt.items() if k not in ('url','signatureCipher','cipher')}
            item['url_present']=bool(fmt.get('url'))
            redacted.append(item)
        sanitized[key]=redacted
    (root / 'video-metadata.json').write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding='utf-8')

segment = root / 'segment-23m00s-25m00s.mp4'
stream_attempts=[]
if metadata and selected_instance:
    formats=[]
    for fmt in metadata.get('formatStreams') or []:
        q = str(fmt.get('qualityLabel') or fmt.get('quality') or '')
        itag = fmt.get('itag')
        height = fmt.get('height') or 0
        formats.append((height, q, itag, fmt.get('url'), False))
    for fmt in metadata.get('adaptiveFormats') or []:
        mime=str(fmt.get('type') or fmt.get('mimeType') or '')
        if mime.startswith('video/'):
            q=str(fmt.get('qualityLabel') or fmt.get('quality') or '')
            itag=fmt.get('itag')
            height=fmt.get('height') or 0
            formats.append((height,q,itag,fmt.get('url'),True))
    formats.sort(key=lambda x: (x[0] <= 720, x[0], not x[4]), reverse=True)
    candidates=[]
    for height,q,itag,direct,video_only in formats:
        if itag is not None:
            candidates.append((f'{selected_instance}/latest_version?id={video_id}&itag={itag}&local=true', f'proxy-itag-{itag}-{q}', height))
        if direct:
            candidates.append((direct, f'direct-itag-{itag}-{q}', height))
    seen=set()
    for media_url,label,height in candidates[:16]:
        if not media_url or media_url in seen: continue
        seen.add(media_url)
        entry={'label':label,'height':height}
        try:
            cmd=['ffmpeg','-y','-loglevel','warning','-ss',str(start_s),'-i',media_url,'-t',str(end_s-start_s),'-an','-vf',"scale='min(1280,iw)':-2",'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(segment)]
            done=subprocess.run(cmd,text=True,capture_output=True,timeout=360)
            entry.update({'returncode':done.returncode,'stderr_tail':done.stderr[-2000:]})
            if done.returncode==0 and segment.exists() and segment.stat().st_size>150000:
                entry.update({'status':'success','bytes':segment.stat().st_size})
                stream_attempts.append(entry)
                break
            entry['status']='failed'
            if segment.exists(): segment.unlink()
        except Exception as exc:
            entry.update({'status':'exception','error':repr(exc)})
            if segment.exists(): segment.unlink()
        stream_attempts.append(entry)
(root / 'stream-attempts.json').write_text(json.dumps(stream_attempts, ensure_ascii=False, indent=2), encoding='utf-8')

if segment.exists():
    subprocess.run(['ffmpeg','-y','-loglevel','warning','-i',str(segment),'-vf','fps=1/10','-q:v','2',str(frames_dir/'frame-%03d.jpg')],check=False,timeout=180)
    subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(segment)],text=True,stdout=(root/'ffprobe.json').open('w'),timeout=30)

# Storyboards are a second independent path and often work even when media streams do not.
storyboard_records=[]
if metadata and metadata.get('storyboards'):
    boards=metadata['storyboards']
    boards=sorted(boards,key=lambda b:(b.get('width') or 0)*(b.get('height') or 0),reverse=True)
    board=boards[0]
    interval=float(board.get('interval') or board.get('interval ') or 10000)
    cols=int(board.get('storyboardWidth') or board.get('columns') or 5)
    rows=int(board.get('storyboardHeight') or board.get('rows') or 5)
    count=int(board.get('count') or 0)
    template=board.get('templateUrl') or board.get('url')
    for second in range(start_s,end_s+1,10):
        frame_index=min(max(int((second*1000)//interval),0),max(count-1,0)) if count else int((second*1000)//interval)
        per_sheet=cols*rows
        sheet_index=frame_index//per_sheet
        pos=frame_index%per_sheet
        tile_url=template
        for token,repl in [('$M',str(sheet_index)),('$N',f'M{sheet_index}'),('$L',str(board.get('level') or 0))]:
            if tile_url: tile_url=tile_url.replace(token,repl)
        if tile_url and tile_url.startswith('/'):
            tile_url=selected_instance+tile_url
        rec={'second':second,'frame_index':frame_index,'sheet_index':sheet_index,'position':pos,'tile_url_present':bool(tile_url)}
        try:
            r=session.get(tile_url,timeout=30)
            rec.update({'http_status':r.status_code,'bytes':len(r.content)})
            r.raise_for_status()
            sheet=Image.open(io.BytesIO(r.content)).convert('RGB')
            cell_w=int(board.get('width') or sheet.width//cols)
            cell_h=int(board.get('height') or sheet.height//rows)
            col=pos%cols; row=pos//cols
            crop=sheet.crop((col*cell_w,row*cell_h,(col+1)*cell_w,(row+1)*cell_h))
            crop=crop.resize((cell_w*4,cell_h*4),Image.Resampling.LANCZOS)
            out=sb_dir/f'storyboard-{second:05d}s.jpg'
            crop.save(out,'JPEG',quality=94,optimize=True)
            rec.update({'status':'success','path':str(out),'cell_width':cell_w,'cell_height':cell_h,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
        except Exception as exc:
            rec.update({'status':'failed','error':repr(exc)})
        storyboard_records.append(rec)
(root / 'storyboard-records.json').write_text(json.dumps(storyboard_records, ensure_ascii=False, indent=2), encoding='utf-8')

actual_frames=sorted(frames_dir.glob('*.jpg'))
storyboard_frames=sorted(sb_dir.glob('*.jpg'))
chosen=actual_frames if actual_frames else storyboard_frames
if chosen:
    thumb_w,thumb_h=640,360; cols=2; rows=math.ceil(len(chosen)/cols)
    sheet=Image.new('RGB',(thumb_w*cols,thumb_h*rows),'white'); draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(chosen):
        im=Image.open(path).convert('RGB'); im.thumbnail((thumb_w,thumb_h)); canvas=Image.new('RGB',(thumb_w,thumb_h),'black'); canvas.paste(im,((thumb_w-im.width)//2,(thumb_h-im.height)//2)); x=(i%cols)*thumb_w; y=(i//cols)*thumb_h; sheet.paste(canvas,(x,y)); draw.text((x+8,y+8),path.stem,fill='white',stroke_width=2,stroke_fill='black')
    sheet.save(root/'contact-sheet.jpg','JPEG',quality=90,optimize=True)

hashes={hashlib.sha256(p.read_bytes()).hexdigest() for p in chosen}
result={
    'status':'actual_segment_frames_captured' if actual_frames else ('actual_storyboard_frames_captured' if storyboard_frames else 'failed'),
    'video_id':video_id,'selected_instance':selected_instance,
    'source_start_seconds':start_s,'source_end_seconds':end_s,
    'segment_exists':segment.exists(),'segment_bytes':segment.stat().st_size if segment.exists() else 0,
    'actual_frame_count':len(actual_frames),'storyboard_frame_count':len(storyboard_frames),
    'chosen_frame_count':len(chosen),'unique_chosen_hashes':len(hashes),
    'chosen_files':[str(p.relative_to(root)) for p in chosen],
}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

payload=io.BytesIO()
with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED) as zf:
    for name in ['result.json','instance-attempts.json','video-metadata.json','stream-attempts.json','storyboard-records.json','ffprobe.json','contact-sheet.jpg']:
        p=root/name
        if p.exists(): zf.write(p,name)
    for p in chosen: zf.write(p,str(p.relative_to(root)))
raw=payload.getvalue(); enc=base64.b64encode(raw).decode('ascii'); chunk=3000; parts=[enc[i:i+chunk] for i in range(0,len(enc),chunk)]
for i,part in enumerate(parts):(root/'transfer'/f'part-{i:04d}.txt').write_text(part,encoding='ascii')
(root/'transfer-manifest.json').write_text(json.dumps({'zip_bytes':len(raw),'base64_chars':len(enc),'chunk_size':chunk,'chunk_count':len(parts),'sha256':hashlib.sha256(raw).hexdigest(),'parts':[f'part-{i:04d}.txt' for i in range(len(parts))]},indent=2),encoding='utf-8')
