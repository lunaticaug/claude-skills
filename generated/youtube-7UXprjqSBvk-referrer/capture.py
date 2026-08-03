import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
from playwright.sync_api import sync_playwright

root = Path('generated/youtube-7UXprjqSBvk-referrer')
frames_dir = root / 'frames'
transfer = root / 'transfer'
targets = [1380, 1395, 1410, 1430, 1460, 1500, 1560, 1620]
records = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--autoplay-policy=no-user-gesture-required', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        locale='ko-KR',
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    )
    page = context.new_page()
    console_messages = []
    page.on('console', lambda msg: console_messages.append({'type': msg.type, 'text': msg.text}))
    page.on('requestfailed', lambda req: console_messages.append({'type': 'requestfailed', 'text': f'{req.url} :: {req.failure}'}))

    for index, second in enumerate(targets, 1):
        candidates = []
        for host in ('youtube', 'nocookie'):
            url = f'http://127.0.0.1:8765/player.html?start={second}&host={host}'
            item = {'source_second': second, 'host': host, 'url': url}
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=45000)
                page.wait_for_timeout(9000)
                iframe = page.locator('iframe')
                # Ask the player to start in case autoplay policy delayed it.
                page.evaluate("""() => {
                  const f = document.querySelector('iframe');
                  if (f && f.contentWindow) {
                    f.contentWindow.postMessage(JSON.stringify({event:'command',func:'mute',args:[]}), '*');
                    f.contentWindow.postMessage(JSON.stringify({event:'command',func:'playVideo',args:[]}), '*');
                  }
                }""")
                page.wait_for_timeout(2500)
                png_path = frames_dir / f'candidate-{index:03d}-{host}-{second:05d}s.png'
                page.screenshot(path=str(png_path), full_page=False)
                image = Image.open(png_path).convert('RGB')
                stat = ImageStat.Stat(image)
                score = sum(stat.stddev) + min(png_path.stat().st_size / 6000, 180)
                item.update({
                    'status': 'captured',
                    'path': str(png_path),
                    'bytes': png_path.stat().st_size,
                    'sha256': hashlib.sha256(png_path.read_bytes()).hexdigest(),
                    'mean_rgb': [round(v, 2) for v in stat.mean],
                    'stddev_rgb': [round(v, 2) for v in stat.stddev],
                    'visual_score': round(score, 3),
                    'iframe_src': iframe.get_attribute('src'),
                })
                candidates.append((score, item, image.copy()))
            except Exception as exc:
                item.update({'status': 'failed', 'error': repr(exc)})
            records.append(item)

        if candidates:
            score, selected, image = max(candidates, key=lambda x: x[0])
            selected['selected'] = True
            jpg_path = frames_dir / f'frame-{index:03d}-{second:05d}s.jpg'
            image.save(jpg_path, 'JPEG', quality=90, optimize=True)

    browser.close()

selected = sorted(frames_dir.glob('frame-*.jpg'))
thumb_w, thumb_h = 640, 360
contact = Image.new('RGB', (thumb_w * 2, thumb_h * 4), 'white')
draw = ImageDraw.Draw(contact)
for i, path in enumerate(selected[:8]):
    image = Image.open(path).convert('RGB').resize((thumb_w, thumb_h))
    x = (i % 2) * thumb_w
    y = (i // 2) * thumb_h
    contact.paste(image, (x, y))
    draw.rectangle((x + 4, y + 4, x + 175, y + 28), fill='black')
    draw.text((x + 10, y + 8), path.stem, fill='white')
contact_path = root / 'contact-sheet.jpg'
contact.save(contact_path, 'JPEG', quality=88, optimize=True)

hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in selected}
result = {
    'status': 'captured',
    'video_id': '7UXprjqSBvk',
    'source_start_seconds': 1380,
    'source_end_seconds': 1620,
    'selected_frame_count': len(selected),
    'unique_selected_hashes': len(hashes),
    'selected_files': [p.name for p in selected],
    'contact_sheet': contact_path.name,
}
(root / 'capture-records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'browser-events.json').write_text(json.dumps(console_messages, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

payload = io.BytesIO()
with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(contact_path, contact_path.name)
    zf.write(root / 'result.json', 'result.json')
    zf.write(root / 'capture-records.json', 'capture-records.json')
    zf.write(root / 'browser-events.json', 'browser-events.json')
    for path in selected:
        zf.write(path, f'frames/{path.name}')
raw = payload.getvalue()
encoded = base64.b64encode(raw).decode('ascii')
chunk_size = 40000
chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
for i, chunk in enumerate(chunks):
    (transfer / f'part-{i:04d}.txt').write_text(chunk, encoding='ascii')
manifest = {
    'zip_bytes': len(raw),
    'base64_chars': len(encoded),
    'chunk_size': chunk_size,
    'chunk_count': len(chunks),
    'sha256': hashlib.sha256(raw).hexdigest(),
    'parts': [f'part-{i:04d}.txt' for i in range(len(chunks))],
}
(root / 'transfer-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
