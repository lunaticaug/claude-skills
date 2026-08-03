import base64, hashlib, json
from pathlib import Path
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright
root=Path('generated/youtube-7UXprjqSBvk-rawgithack')
url='https://raw.githack.com/lunaticaug/claude-skills/82e2251cc0b70621f45e0dc979ddaa2cbadd98df/tools/cpptx-youtube-player.html?start=1380'
events=[]
with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(root/'profile'),executable_path='/usr/bin/google-chrome',headless=False,viewport={'width':1280,'height':720},ignore_default_args=['--enable-automation'],args=['--autoplay-policy=no-user-gesture-required','--disable-blink-features=AutomationControlled','--disable-dev-shm-usage'])
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page=context.pages[0]
    page.on('console',lambda m:events.append({'type':f'console:{m.type}','text':m.text[:1500]}))
    page.on('requestfailed',lambda r:events.append({'type':'requestfailed','text':f'{r.url} :: {r.failure}'[:1500]}))
    response=page.goto(url,wait_until='domcontentloaded',timeout=90000)
    page.wait_for_timeout(16000)
    initial=page.evaluate("() => ({title:document.title,href:location.href,state:window.__ytState||null,iframe:document.querySelector('iframe')?.src||null,body:(document.body?.innerText||'').slice(0,2000)})")
    seek=page.evaluate("async () => window.seekAndPause ? await window.seekAndPause(1380) : ({ok:false,reason:'missing'})")
    page.wait_for_timeout(1500)
    iframe=page.locator('iframe').first
    if iframe.is_visible(timeout=3000): iframe.screenshot(path=str(root/'frame-01380s.png'))
    else: page.screenshot(path=str(root/'frame-01380s.png'))
    context.close()
image=Image.open(root/'frame-01380s.png').convert('RGB'); stat=ImageStat.Stat(image)
result={'status':'actual_frame_captured' if seek.get('ok') and seek.get('duration',0)>0 and abs(seek.get('currentTime',0)-1380)<15 else 'failed','http_status':response.status if response else None,'initial':initial,'seek':seek,'frame_bytes':(root/'frame-01380s.png').stat().st_size,'mean_rgb':[round(v,2) for v in stat.mean],'stddev_rgb':[round(v,2) for v in stat.stddev]}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
image.save(root/'frame-01380s.jpg','JPEG',quality=90,optimize=True)
raw=(root/'frame-01380s.jpg').read_bytes(); enc=base64.b64encode(raw).decode('ascii'); size=3000; parts=[enc[i:i+size] for i in range(0,len(enc),size)]
for i,part in enumerate(parts):(root/'transfer'/f'part-{i:03d}.txt').write_text(part,encoding='ascii')
(root/'transfer-manifest.json').write_text(json.dumps({'bytes':len(raw),'base64_chars':len(enc),'chunk_size':size,'chunk_count':len(parts),'sha256':hashlib.sha256(raw).hexdigest(),'parts':[f'part-{i:03d}.txt' for i in range(len(parts))]},indent=2),encoding='utf-8')
