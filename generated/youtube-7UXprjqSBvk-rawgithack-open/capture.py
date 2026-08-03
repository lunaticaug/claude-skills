import base64, hashlib, io, json, zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
from playwright.sync_api import sync_playwright

root=Path('generated/youtube-7UXprjqSBvk-rawgithack-open')
frames=root/'frames'
url='https://raw.githack.com/lunaticaug/claude-skills/82e2251cc0b70621f45e0dc979ddaa2cbadd98df/tools/cpptx-youtube-player.html?start=1380'
targets=[1380,1390,1400,1415,1430,1450,1470,1500]
events=[]; records=[]
with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(root/'profile'),executable_path='/usr/bin/google-chrome',headless=False,viewport={'width':1280,'height':720},locale='ko-KR',timezone_id='Asia/Seoul',ignore_default_args=['--enable-automation'],args=['--autoplay-policy=no-user-gesture-required','--disable-blink-features=AutomationControlled','--disable-dev-shm-usage'])
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page=context.pages[0]
    page.on('console',lambda m:events.append({'type':f'console:{m.type}','text':m.text[:2000]}))
    page.on('requestfailed',lambda r:events.append({'type':'requestfailed','text':f'{r.url} :: {r.failure}'[:2000]}))
    response=page.goto(url,wait_until='domcontentloaded',timeout=90000)
    page.wait_for_timeout(1500)
    # rawgit.hack places an interstitial before unreviewed third-party HTML.
    opened=False
    for selector in ["text=Open the page","a:has-text('Open the page')","button:has-text('Open the page')"]:
        try:
            target=page.locator(selector).first
            if target.is_visible(timeout=1200):
                target.click(timeout=5000)
                opened=True
                break
        except Exception:
            pass
    if opened:
        page.wait_for_timeout(3000)
    # Some versions open a new page/tab.
    if len(context.pages)>1:
        page=context.pages[-1]
    page.wait_for_load_state('domcontentloaded',timeout=45000)
    page.wait_for_timeout(15000)
    initial=page.evaluate("() => ({title:document.title,href:location.href,state:window.__ytState||null,iframe:document.querySelector('iframe')?.src||null,body:(document.body?.innerText||'').slice(0,2000)})")
    (root/'initial-state.json').write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding='utf-8')
    page.screenshot(path=str(root/'initial-page.png'))
    for i,second in enumerate(targets,1):
        rec={'source_second':second}
        try:
            seek=page.evaluate("async s => window.seekAndPause ? await window.seekAndPause(s) : ({ok:false,reason:'missing',state:window.__ytState})",second)
            page.wait_for_timeout(1000)
            shot=frames/f'frame-{i:03d}-{second:05d}s.png'
            iframe=page.locator('iframe').first
            if iframe.is_visible(timeout=2500): iframe.screenshot(path=str(shot),timeout=30000)
            else: page.screenshot(path=str(shot))
            im=Image.open(shot).convert('RGB'); st=ImageStat.Stat(im)
            valid=bool(seek.get('ok') and seek.get('duration',0)>0 and abs(seek.get('currentTime',0)-second)<15)
            rec.update({'status':'captured' if valid else 'player_error_frame','seek':seek,'path':str(shot),'bytes':shot.stat().st_size,'sha256':hashlib.sha256(shot.read_bytes()).hexdigest(),'width':im.width,'height':im.height,'mean_rgb':[round(v,2) for v in st.mean],'stddev_rgb':[round(v,2) for v in st.stddev]})
        except Exception as exc:
            rec.update({'status':'failed','error':repr(exc)})
        records.append(rec)
    context.close()
(root/'capture-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'browser-events.json').write_text(json.dumps(events[-500:],ensure_ascii=False,indent=2),encoding='utf-8')
good=[r for r in records if r.get('status')=='captured']; hashes={r['sha256'] for r in good}; paths=[Path(r['path']) for r in good]
sheet_paths=paths or [Path(r['path']) for r in records if r.get('path')]
if sheet_paths:
    sheet=Image.new('RGB',(1280,360*((len(sheet_paths)+1)//2)),'white'); draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(sheet_paths):
        im=Image.open(path).convert('RGB'); im.thumbnail((640,360)); canvas=Image.new('RGB',(640,360),'black'); canvas.paste(im,((640-im.width)//2,(360-im.height)//2)); x=(i%2)*640; y=(i//2)*360; sheet.paste(canvas,(x,y)); draw.text((x+8,y+8),path.stem,fill='white',stroke_width=2,stroke_fill='black')
    sheet.save(root/'contact-sheet.jpg','JPEG',quality=90,optimize=True)
result={'status':'actual_video_frames_captured' if len(good)>=2 and len(hashes)>=2 else 'failed','video_id':'7UXprjqSBvk','source_start_seconds':1380,'source_end_seconds':1500,'interstitial_opened':opened,'valid_frame_count':len(good),'unique_valid_hashes':len(hashes),'valid_files':[p.name for p in paths]}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
payload=io.BytesIO()
with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED) as zf:
    for name in ['result.json','initial-state.json','capture-records.json','browser-events.json','contact-sheet.jpg','initial-page.png']:
        p=root/name
        if p.exists(): zf.write(p,name)
    for p in paths: zf.write(p,f'frames/{p.name}')
raw=payload.getvalue(); enc=base64.b64encode(raw).decode('ascii'); size=3000; parts=[enc[i:i+size] for i in range(0,len(enc),size)]
for i,part in enumerate(parts):(root/'transfer'/f'part-{i:04d}.txt').write_text(part,encoding='ascii')
(root/'transfer-manifest.json').write_text(json.dumps({'zip_bytes':len(raw),'base64_chars':len(enc),'chunk_size':size,'chunk_count':len(parts),'sha256':hashlib.sha256(raw).hexdigest(),'parts':[f'part-{i:04d}.txt' for i in range(len(parts))]},indent=2),encoding='utf-8')
