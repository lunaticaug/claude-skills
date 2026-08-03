import base64
import hashlib
import json
import subprocess
from pathlib import Path
import requests
from PIL import Image, ImageStat

root = Path('generated/youtube-7UXprjqSBvk-cobalt-probe')
source_url = 'https://www.youtube.com/watch?v=7UXprjqSBvk'
response_data = None
media_url = None
error = None
try:
    response = requests.post(
        'http://127.0.0.1:19000/',
        headers={'Accept':'application/json','Content-Type':'application/json'},
        json={
            'url': source_url,
            'videoQuality': '480',
            'downloadMode': 'mute',
            'youtubeVideoCodec': 'h264',
            'youtubeVideoContainer': 'mp4',
            'localProcessing': 'forced',
            'alwaysProxy': True,
            'disableMetadata': True,
        },
        timeout=180,
    )
    (root/'http-status.txt').write_text(str(response.status_code), encoding='utf-8')
    (root/'cobalt-response.json').write_text(response.text, encoding='utf-8')
    response.raise_for_status()
    response_data = response.json()
    status = response_data.get('status') if isinstance(response_data, dict) else None
    if status in {'tunnel','redirect'}:
        media_url = response_data.get('url')
    elif status == 'local-processing':
        tunnels = response_data.get('tunnel') or []
        if tunnels:
            media_url = tunnels[0]
except Exception as exc:
    error = repr(exc)
    (root/'probe-exception.txt').write_text(error, encoding='utf-8')

ffmpeg_code = None
if media_url:
    cmd = [
        'ffmpeg','-y','-ss','1380','-i',media_url,
        '-frames:v','1','-vf',"scale='min(1280,iw)':-2",
        '-q:v','2',str(root/'frame-01380s.jpg')
    ]
    try:
        done = subprocess.run(cmd, text=True, capture_output=True, timeout=360)
        ffmpeg_code = done.returncode
        log = (done.stdout + '\n' + done.stderr).replace(media_url, '<redacted-media-url>')
        (root/'ffmpeg.log').write_text(log[-40000:], encoding='utf-8')
    except Exception as exc:
        error = (error + '; ' if error else '') + repr(exc)
        (root/'ffmpeg-exception.txt').write_text(repr(exc), encoding='utf-8')

frame = root/'frame-01380s.jpg'
result = {
    'status': 'frame_captured' if frame.exists() and frame.stat().st_size > 10000 else 'failed',
    'video_id': '7UXprjqSBvk',
    'source_second': 1380,
    'session_ready': (root/'session-ready.txt').read_text().strip() == '1',
    'cobalt_ready': (root/'cobalt-ready.txt').read_text().strip() == '1',
    'cobalt_status': response_data.get('status') if isinstance(response_data, dict) else None,
    'cobalt_error': response_data.get('error') if isinstance(response_data, dict) else None,
    'media_url_resolved': bool(media_url),
    'ffmpeg_code': ffmpeg_code,
    'error': error,
}
if frame.exists():
    image = Image.open(frame).convert('RGB')
    stat = ImageStat.Stat(image)
    result.update({
        'frame_bytes': frame.stat().st_size,
        'width': image.width,
        'height': image.height,
        'mean_rgb': [round(v,2) for v in stat.mean],
        'stddev_rgb': [round(v,2) for v in stat.stddev],
        'sha256': hashlib.sha256(frame.read_bytes()).hexdigest(),
    })
    encoded = base64.b64encode(frame.read_bytes()).decode('ascii')
    chunk_size = 3000
    parts = [encoded[i:i+chunk_size] for i in range(0,len(encoded),chunk_size)]
    for i, part in enumerate(parts):
        (root/'transfer'/f'part-{i:03d}.txt').write_text(part, encoding='ascii')
    (root/'transfer-manifest.json').write_text(json.dumps({
        'bytes': frame.stat().st_size,
        'base64_chars': len(encoded),
        'chunk_size': chunk_size,
        'chunk_count': len(parts),
        'sha256': hashlib.sha256(frame.read_bytes()).hexdigest(),
        'parts': [f'part-{i:03d}.txt' for i in range(len(parts))],
    }, indent=2), encoding='utf-8')
(root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
