"""Generic Augmintech blog builder. Usage: python3 build_blog.py <config.json>
Writes <out>/<slug>.html (with __IMG_n__ placeholders) and <out>/images/*.webp, prints a short report."""
import re, sys, json, base64, io, os, html as H
from PIL import Image

cfg = json.load(open(sys.argv[1]))
s = open(cfg['src'], encoding='utf-8').read()
slug = cfg['slug']
W = '#aug-' + re.sub(r'[^a-z0-9]+', '-', slug)
OUT = cfg['out']; os.makedirs(OUT + '/images', exist_ok=True)
report = {'slug': slug}


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:90])
    s = s.replace(old, new)


# --- editor comments ---
s, n = re.subn(r'<!--\s*EDITOR NOTE.*?-->\s*', '', s, flags=re.S); report['editor_notes_removed'] = n

# --- CSS scoping ---
a, b = s.index('<style>') + 7, s.index('</style>')
css = s[a:b]
css = re.sub(r"@import url\([^)]*\);\n?", '', css)
css = css.replace('html{scroll-behavior:smooth;}\n', '')
css = re.sub(r'#progress\{[^}]*\}\n?', '', css)
css = css.replace("--display:'Manrope',sans-serif;--body:'Inter',system-ui,sans-serif;--mono:'IBM Plex Mono',monospace;",
                  "--display:inherit;--body:inherit;--mono:inherit;")


def scope_sel(sel):
    sel = sel.strip()
    if sel in (':root', 'body'): return W
    if sel == '.blog': return W + '.blog'
    if sel == '*': return W + ' *'
    return W + ' ' + sel


def scope(block):
    out, i = [], 0
    while i < len(block):
        j = block.find('{', i)
        if j < 0: out.append(block[i:]); break
        head = block[i:j]
        if head.strip().startswith('@media'):
            depth, k = 1, j + 1
            while depth:
                depth += {'{': 1, '}': -1}.get(block[k], 0); k += 1
            out.append(head + '{' + scope(block[j + 1:k - 1]) + '}'); i = k; continue
        if head.strip().startswith('@keyframes'):
            depth, k = 1, j + 1
            while depth:
                depth += {'{': 1, '}': -1}.get(block[k], 0); k += 1
            out.append(block[i:k]); i = k; continue
        k = block.index('}', j)
        lead = head[:len(head) - len(head.lstrip())]
        body = head.strip()
        com = ''
        while body.startswith('/*'):  # keep comments out of selectors
            e = body.index('*/') + 2; com += body[:e]; body = body[e:].strip()
        out.append(lead + com + ','.join(scope_sel(x) for x in body.split(',')) + block[j:k + 1])
        i = k + 1
    return ''.join(out)


css = scope(css)
css += f"""
/* ===== Augmintech theme overrides ===== */
{W}.blog{{max-width:none;margin:0;padding:0 0 1rem;}}
{W} h2{{font-size:28px;color:#1a1a1a;border-top:1px solid #e5e5e5;}}
{W} a{{color:#0F4C81;border-bottom:0;text-decoration:underline;text-underline-offset:2px;}}
{W} a:hover{{color:#18d104;}}
{W} .cta{{background:#1a1a1a;}}
{W} .cta a.cta-btn{{text-decoration:none;}}
{W} .cta-btn-blue{{background:#18d104;color:#000;}}
{W} .cta-btn-blue:hover{{background:#12b803;color:#000;}}
{W} [class^="aug-cta-banner"] a{{color:#fff;text-decoration:none;}}
"""
s = s[:a] + css + s[b:]

# --- wrapper, progress, hero ---
rep('<div id="progress"></div>\n<div class="blog">', f'<div class="blog" id="{W[1:]}">')
s, n = re.subn(r'<p class="eyebrow">.*?</p>\s*', '', s, count=1, flags=re.S); assert n == 1
m = re.search(r'<h1 class="hero-title">(.*?)</h1>\s*', s, re.S); report['h1'] = H.unescape(re.sub('<[^>]+>', '', m.group(1)))
s = s[:m.start()] + s[m.end():]
s, n = re.subn(r'\n<div class="meta">.*?</div>\n', '\n', s, count=1, flags=re.S); assert n == 1

# --- progress script ---
s = s.replace("""window.addEventListener('scroll', () => {
  const el = document.getElementById('progress');
  const total = document.body.scrollHeight - window.innerHeight;
  if (total > 0) el.style.width = (window.scrollY / total * 100) + '%';
});
""", '')
s = re.sub(r'<script>\s*</script>\s*', '', s)

# --- images: data URIs -> webp files + placeholders ---
imgs = []
def img_sub(m):
    tag = m.group(0)
    src = re.search(r'src="(data:image/([a-z+]+);base64,([^"]+))"', tag)
    if not src: return tag
    alt = (re.search(r'alt="([^"]*)"', tag) or [None, 'image'])[1]
    words = re.sub(r'[^a-z0-9 ]', '', H.unescape(alt).lower()).split()[:5]
    name = f"{cfg['prefix']}-{'-'.join(words)}.webp"
    k = 2
    while any(i['file'] == name for i in imgs):  # same alt twice -> unique file name
        name = f"{cfg['prefix']}-{'-'.join(words)}-{k}.webp"; k += 1
    raw = base64.b64decode(src.group(3))
    if src.group(2) == 'svg+xml':
        wd = int((re.search(r'width="(\d+)"', tag) or [0, 1200])[1])
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch(); pg = br.new_page(device_scale_factor=2)
            pg.set_content(f'<html><body style="margin:0;background:#fff">{raw.decode("utf-8")}</body></html>')
            el = pg.query_selector('svg'); el.evaluate(f"e=>{{e.style.width='{wd}px';e.style.height='auto';e.style.display='block'}}")
            png = el.screenshot(); br.close()
        im = Image.open(io.BytesIO(png)).convert('RGB')
        if im.width > 1600: im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    else:
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        if im.width > 1200: im = im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS)
    im.save(OUT + '/images/' + name, 'WEBP', quality=65, method=6)
    imgs.append({'file': name, 'alt': H.unescape(alt), 'bytes': os.path.getsize(OUT + '/images/' + name), 'kb_before': len(src.group(1)) // 1024})
    return tag.replace(src.group(1), f'__IMG{len(imgs)}__')
s = re.sub(r'<img[^>]*>', img_sub, s)
report['images'] = imgs

# --- banner ---
ban = open(cfg['banner'], encoding='utf-8').read()
ban = ban[ban.index('<style>'):].replace('&amp;utm_source=chatgpt.com', '').replace('&utm_source=chatgpt.com', '').strip()
rep(cfg['banner_before'], ban + '\n\n' + cfg['banner_before'])

# --- custom replacements (CTA text, WhatsApp buttons, etc.) ---
for old, new in cfg.get('replace', []):
    rep(old, new)

# --- internal links: (exact text in a paragraph, anchor, slug) ---
links = []
for ctx, anchor, target in cfg['links']:
    assert anchor in ctx, anchor
    rep(ctx, ctx.replace(anchor, f'<a href="https://augmintech.com/{target}/">{anchor}</a>', 1))
    links.append(f'{anchor} -> /{target}/')
report['internal_links'] = links

# --- course links ---
course = cfg['course_url']
found = sorted(set(re.findall(r'https://augmintech\.com/courses/[^"\']+', s)))
report['course_links_found'] = found
for u in found:
    if u != course: s = s.replace(u, course)
report['course_links_changed'] = [u for u in found if u != course]

# --- checks ---
report['whatsapp_links_left'] = len(re.findall(r'wa\.me/', s))  # banner has 1
assert not re.search(r'data:image/[^"\'\s]{200,}', s) and 'progress' not in s, 'leftover data URI / progress'
for t in ('div', 'script', 'style', 'table', 'figure', 'ul', 'section', 'details'):
    assert s.count('<' + t) == s.count('</' + t + '>') or t == 'details', t
open(f'{OUT}/{slug}.html', 'w', encoding='utf-8').write(s)
report['html_kb'] = len(s.encode()) // 1024
print(json.dumps(report, indent=1, ensure_ascii=False))
