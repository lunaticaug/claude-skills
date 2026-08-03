import base64, hashlib, json, shutil
from pathlib import Path
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

root=Path('generated/youtube-7UXprjqSBvk-referrer-probe')
chrome=(shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium') or shutil.which('chromium-browser'))
events=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path=chrome, args=['--autoplay-policy=no-user-gesture-required','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1280,'height':720}, locale='ko-KR')
    page.on('console', lambda m: events.append({'type':m.type,'text':m.text}))
    page.on('requestfailed', lambda r: events.append({'type':'requestfailed','text':f'{r.url} :: {r.failure}'}))
    page.goto('http://127.0.0.1:8765/index.html', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(11000)
    page.screenshot(path=str(root/'frame-01380s.png'))
    browser.close()
image=Image.open(root/'frame-01380s.png').convert('RGB')
image.save(root/'frame-01380s.jpg','JPEG',quality=90,optimize=True)
stat=ImageStat.Stat(image)
result={
    'status':'captured','video_id':'7UXprjqSBvk','source_second':1380,'chrome':chrome,
    'png_bytes':(root/'frame-01380s.png').stat().st_size,
    'jpg_bytes':(root/'frame-01380s.jpg').stat().st_size,
    'mean_rgb':[round(v,2) for v in stat.mean],
    'stddev_rgb':[round(v,2) for v in stat.stddev],
    'sha256':hashlib.sha256((root/'frame-01380s.jpg').read_bytes()).hexdigest(),
}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
payload=(root/'frame-01380s.jpg').read_bytes()
encoded=base64.b64encode(payload).decode('ascii')
size=30000
parts=[encoded[i:i+size] for i in range(0,len(encoded),size)]
for i,part in enumerate(parts):
    (root/'transfer'/f'part-{i:03d}.txt').write_text(part,encoding='ascii')
(root/'transfer-manifest.json').write_text(json.dumps({
    'bytes':len(payload),'base64_chars':len(encoded),'chunk_count':len(parts),
    'sha256':hashlib.sha256(payload).hexdigest(),
    'parts':[f'part-{i:03d}.txt' for i in range(len(parts))]
},indent=2),encoding='utf-8')
