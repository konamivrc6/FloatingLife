"""
浮生 — 静态站点生成器
解析正文和设定集 Markdown 文件，生成完整静态站点到 docs/
"""
import os
import re
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
NOVEL = BASE / "浮生 · 满梧.md"
SETTINGS_DIR = BASE / "BgSettings"
DOCS = BASE / "docs"

# ── HTML 模板 ──────────────────────────────────────────────

CSS = r"""
:root {
  --bg: #fff;
  --text: #000;
  --muted: #666;
  --accent: #000;
  --border: #ccc;
  --card-bg: #fff;
  --hover: #f2f2f2;
  --max-w: 720px;
}
[data-theme="dark"] {
  --bg: #000;
  --text: #fff;
  --muted: #999;
  --accent: #fff;
  --border: #333;
  --card-bg: #000;
  --hover: #1a1a1a;
}
.theme-toggle {
  position: fixed;top:1rem;right:1rem;
  background:none;border:1px solid var(--border);cursor:pointer;
  z-index:100;padding:.4rem;line-height:1;border-radius:8px;
  transition:transform .2s;color:var(--text);
}
.theme-toggle:hover{transform:scale(1.2)}
.icon-sun{display:none}
.icon-moon{display:block}
[data-theme="dark"] .icon-sun{display:block}
[data-theme="dark"] .icon-moon{display:none}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:17px;line-height:1.75}
body{
  font-family:"Noto Serif SC","Source Han Serif SC","Songti SC",Georgia,serif;
  background:var(--bg);color:var(--text);
  min-height:100vh;display:flex;flex-direction:column;
}
main{flex:1;max-width:var(--max-w);width:100%;margin:0 auto;padding:3rem 1.5rem}
h1{font-size:2.2rem;text-align:center;margin:2rem 0 1.5rem;letter-spacing:.08em;font-weight:700}
h2{font-size:1.5rem;margin:2rem 0 1rem;font-weight:600;color:var(--accent)}
h3{font-size:1.2rem;margin:1.5rem 0 .75rem;font-weight:600}
h4{font-size:1.05rem;margin:1.2rem 0 .6rem;font-weight:600}
p{margin:0 0 1em;text-align:justify}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:"JetBrains Mono","Fira Code",monospace;font-size:.88rem;background:var(--hover);padding:.15em .35em;border-radius:4px}
pre{background:var(--hover);padding:1rem 1.2rem;border-radius:8px;overflow-x:auto;margin:1rem 0;border:1px solid var(--border)}
pre code{background:none;padding:0;font-size:.82rem;line-height:1.6;white-space:pre-wrap;word-break:break-word}
blockquote{border-left:3px solid var(--accent);padding:.5rem 1.2rem;margin:1rem 0;color:var(--muted);font-style:italic}
ul,ol{margin:.5rem 0 1rem 1.5rem}
li{margin:.3rem 0}
hr{border:none;border-top:1px solid var(--border);margin:2.5rem 0}
nav{display:flex;align-items:center;gap:1rem;margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid var(--border)}
nav a{font-size:.95rem}
nav .sep{color:var(--muted)}
.btn-group{display:flex;gap:1.5rem;justify-content:center;margin:3rem 0}
.btn{
  display:inline-block;padding:.85rem 0;font-size:1.15rem;width:10rem;
  border:2px solid var(--accent);border-radius:8px;color:var(--accent);
  background:transparent;cursor:pointer;transition:all .2s;
  text-align:center;font-family:inherit;
}
.btn:hover{background:var(--accent);color:var(--bg);text-decoration:none}
.btn.primary{background:var(--accent);color:var(--bg)}
.btn.primary:hover{opacity:.85}
.toc-list{list-style:none;margin:0;padding:0}
.toc-list li{border-bottom:1px solid var(--border)}
.toc-list a{display:block;padding:.9rem 1rem;font-size:1.1rem;transition:background .15s;border-radius:6px}
.toc-list a:hover{background:var(--hover);text-decoration:none}
.toc-num{display:inline-block;width:2.5rem;color:var(--muted);font-size:.9rem}
.footer{text-align:center;color:var(--muted);font-size:.85rem;padding:2rem 0;border-top:1px solid var(--border);margin-top:3rem}
.chapter-content h2{margin-top:0}
.chapter-nav{display:flex;justify-content:space-between;margin:3rem 0 1rem;padding-top:2rem;border-top:1px solid var(--border)}
.chapter-nav a{font-size:1rem}
.home-title{font-size:4rem;letter-spacing:.15em;font-weight:900;text-align:center;margin:6rem 0 1rem}
.home-sub{text-align:center;color:var(--muted);font-size:1.1rem;margin-bottom:2rem}
"""

PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — 浮生</title>
<style>{css}</style>
</head>
<body>
<button class="theme-toggle" id="themeToggle" title="切换亮色/暗色模式">
<svg class="icon-sun" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
<svg class="icon-moon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
</button>
<main>
{nav}
{body}
</main>
<script>
const toggle = document.getElementById('themeToggle');
function getTheme() {{
  const saved = localStorage.getItem('theme');
  if (saved) return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}}
function applyTheme(t) {{
  document.documentElement.setAttribute('data-theme', t);
}}
applyTheme(getTheme());
toggle.addEventListener('click', () => {{
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', next);
  applyTheme(next);
}});
</script>
</body>
</html>"""

HOME_NAV = ""

CHAPTER_NAV_TPL = """<nav><a href="../chapters.html">← 目录</a><span class="sep">|</span><a href="../index.html">首页</a></nav>"""

SETTING_NAV_TPL = """<nav><a href="../settings.html">← 设定集</a><span class="sep">|</span><a href="../index.html">首页</a></nav>"""

LIST_NAV = """<nav><a href="index.html">← 首页</a></nav>"""

# ── Markdown → HTML ─────────────────────────────────────────

try:
    import markdown as md_lib
    def md_to_html(text):
        return md_lib.markdown(text, extensions=['fenced_code', 'codehilite', 'tables'])
except ImportError:
    # 无 markdown 库时的简易回退
    def md_to_html(text):
        return _simple_md(text)

def _simple_md(text):
    """简易 Markdown 转换，不依赖外部库"""
    lines = text.split('\n')
    out = []
    in_code = False
    in_list = False
    i = 0
    while i < len(lines):
        line = lines[i]
        # 代码块
        if line.strip().startswith('```'):
            if in_code:
                out.append('</code></pre>')
                in_code = False
            else:
                out.append('<pre><code>')
                in_code = True
            i += 1
            continue
        if in_code:
            out.append(_escape(line))
            out.append('\n')
            i += 1
            continue

        stripped = line.strip()

        # 空行
        if not stripped:
            if in_list:
                out.append('</ul>')
                in_list = False
            i += 1
            continue

        # 标题
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            if in_list:
                out.append('</ul>')
                in_list = False
            lvl = len(m.group(1))
            out.append(f'<h{lvl}>{m.group(2)}</h{lvl}>')
            i += 1
            continue

        # 块引用
        if stripped.startswith('> '):
            if in_list:
                out.append('</ul>')
                in_list = False
            out.append(f'<blockquote>{_inline(stripped[2:])}</blockquote>')
            i += 1
            continue

        # 无序列表
        m = re.match(r'^-\s+(.+)$', stripped)
        if m:
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{_inline(m.group(1))}</li>')
            i += 1
            continue

        if in_list:
            out.append('</ul>')
            in_list = False

        # 水平线
        if stripped in ('---', '***', '___'):
            out.append('<hr>')
            i += 1
            continue

        # 普通段落
        out.append(f'<p>{_inline(stripped)}</p>')
        i += 1

    if in_code:
        out.append('</code></pre>')
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)

def _escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _inline(s):
    """行内格式：粗体、斜体、行内代码、链接"""
    # 行内代码（保护）
    codes = []
    def save_code(m):
        codes.append(m.group(1))
        return f'\x00CODE{len(codes)-1}\x00'
    s = re.sub(r'`([^`]+)`', save_code, s)
    # 粗体+斜体
    s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', s)
    # 粗体
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    # 斜体
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    # 链接
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    # 恢复行内代码
    for idx, c in enumerate(codes):
        s = s.replace(f'\x00CODE{idx}\x00', f'<code>{_escape(c)}</code>')
    return s


# ── 章节解析 ────────────────────────────────────────────────

def parse_chapters():
    """解析 浮生 · 满梧.md，按 ## N 标题 分割为章节列表"""
    text = NOVEL.read_text(encoding='utf-8-sig')
    # 去掉 BOM 和首行 "# 浮生" 标题
    text = text.lstrip('﻿')

    parts = re.split(r'(?=^## \d+ )', text, flags=re.MULTILINE)
    chapters = []
    first_title = None
    preamble = None

    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r'^## (\d+)\s+(.+?)$', part, re.MULTILINE)
        if m:
            ch_num = int(m.group(1))
            ch_title = m.group(2).strip()
            # 去掉标题行得到正文
            body_lines = part.split('\n', 1)
            body = body_lines[1] if len(body_lines) > 1 else ''
            chapters.append({
                'num': ch_num,
                'title': ch_title,
                'body': body.strip(),
                'html': md_to_html(body.strip()),
            })
        else:
            # 可能是 preamble（# 浮生 等）
            if not first_title:
                m2 = re.match(r'^#\s+(.+?)$', part, re.MULTILINE)
                if m2:
                    first_title = m2.group(1)
                    preamble = part.split('\n', 1)
                    preamble = preamble[1] if len(preamble) > 1 else ''

    chapters.sort(key=lambda c: c['num'])
    return chapters, first_title or '浮生'


def parse_settings():
    """列出 BgSettings/ 下所有 .md 文件"""
    files = []
    for p in sorted(SETTINGS_DIR.glob('*.md')):
        m = re.match(r'^(\d+)\s+(.+?)\.md$', p.name)
        if m:
            files.append({
                'num': int(m.group(1)),
                'title': m.group(2).strip(),
                'slug': str(p.stem),
                'path': str(p),
            })
    files.sort(key=lambda f: f['num'])
    return files


# ── 页面生成 ────────────────────────────────────────────────

def write_page(rel_path, title, nav, body):
    path = DOCS / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        PAGE_TPL.format(title=title, css=CSS, nav=nav, body=body),
        encoding='utf-8'
    )


def build():
    DOCS.mkdir(exist_ok=True)

    # 1. 解析数据
    chapters, novel_title = parse_chapters()
    settings = parse_settings()

    # 2. 首页
    body = f'''<h1 class="home-title">{novel_title}</h1>
<p class="home-sub">律</p>
<div class="btn-group">
  <a href="chapters.html" class="btn primary">正文</a>
  <a href="settings.html" class="btn">设定集</a>
</div>'''
    write_page('index.html', '首页', HOME_NAV, body)

    # 3. 章节目录页
    toc_items = []
    for ch in chapters:
        toc_items.append(
            f'<li><a href="chapter/{ch["num"]}.html">'
            f'<span class="toc-num">{ch["num"]}</span>{ch["title"]}'
            f'</a></li>'
        )
    body = f'<h1>浮生</h1>\n<ul class="toc-list">\n' + '\n'.join(toc_items) + '\n</ul>'
    write_page('chapters.html', '浮生', LIST_NAV, body)

    # 4. 各章节页
    for ch in chapters:
        prev_link = ''
        next_link = ''
        prev_ch = next((c for c in chapters if c['num'] == ch['num'] - 1), None)
        next_ch = next((c for c in chapters if c['num'] == ch['num'] + 1), None)
        nav_links = ''
        if prev_ch:
            nav_links += f'<a href="{prev_ch["num"]}.html">← {prev_ch["num"]} {prev_ch["title"]}</a>'
        else:
            nav_links += '<span></span>'
        if next_ch:
            nav_links += f'<a href="{next_ch["num"]}.html">{next_ch["num"]} {next_ch["title"]} →</a>'
        else:
            nav_links += '<span></span>'

        body = f'''<h2>{ch["num"]} {ch["title"]}</h2>
<div class="chapter-content">
{ch["html"]}
</div>
<div class="chapter-nav">{nav_links}</div>'''
        write_page(f'chapter/{ch["num"]}.html', f'{ch["num"]} {ch["title"]}', CHAPTER_NAV_TPL, body)

    # 5. 设定集列表页
    setting_items = []
    for s in settings:
        setting_items.append(
            f'<li><a href="setting/{s["slug"]}.html">'
            f'<span class="toc-num">{s["num"]}</span>{s["title"]}'
            f'</a></li>'
        )
    body = f'<h1>设定集</h1>\n<ul class="toc-list">\n' + '\n'.join(setting_items) + '\n</ul>'
    write_page('settings.html', '设定集', LIST_NAV, body)

    # 6. 各设定文档页
    for s in settings:
        raw = Path(s['path']).read_text(encoding='utf-8-sig').lstrip('﻿')
        # 去掉首行 # 标题（页面用 h2 显示）
        lines = raw.split('\n', 1)
        content = lines[1].strip() if len(lines) > 1 else raw
        html = md_to_html(content)
        body = f'<h2>{s["title"]}</h2>\n<div class="chapter-content">\n{html}\n</div>'
        write_page(f'setting/{s["slug"]}.html', s['title'], SETTING_NAV_TPL, body)

    # 7. 复制静态资源（如果有）
    # 目前所有 CSS 内嵌，无需额外资源

    print(f'[OK] Generated {len(chapters)} chapters + {len(settings)} settings docs')
    print(f'  Home: docs/index.html')
    print(f'  TOC:  docs/chapters.html')
    print(f'  Settings: docs/settings.html')


if __name__ == '__main__':
    build()
