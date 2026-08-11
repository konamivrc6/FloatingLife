"""
浮生 — 静态站点生成器
解析正文和设定集 Markdown 文件，生成完整静态站点到 docs/
"""
import math
import random
import re
import shutil
from pathlib import Path

import markdown as md_lib

BASE = Path(__file__).resolve().parent
NOVEL = BASE / "浮生 · 满梧.md"
SETTINGS_DIR = BASE / "[WLD] Worldbuilding Bureau"
DOCS = BASE / "docs"

# ── HTML 模板 ──────────────────────────────────────────────

CSS = r"""
@font-face {
  font-family: 'Noto Sans Runic';
  src: url('fonts/NotoSansRunic.woff2') format('woff2');
  unicode-range: U+16A0-16FF;
  font-display: swap;
}
@font-face {
  font-family: 'Noto Sans Symbols 2';
  src: url('fonts/NotoSansSymbols2.woff2') format('woff2');
  unicode-range: U+1F700-1F77F;
  font-display: swap;
}
/* ===== 浅色：晨雾 ===== */
:root {
  --bg: #fafaf9;
  --bg2: #f2f2f0;
  --text: #1c1c1a;
  --muted: #8c8c88;
  --accent: #6b8299;
  --chroma: #6b8299;
  --chroma-dim: #96a9ba;
  --chroma-bg: rgba(107,130,153,.08);
  --border: rgba(0,0,0,.06);
  --card-bg: #fafaf9;
  --hover: rgba(107,130,153,.08);
  --max-w: 720px;
  --reading-bar: #6b8299;
}
/* ===== 深色：深水 ===== */
[data-theme="dark"] {
  --bg: #14181d;
  --bg2: #1a1e24;
  --text: #e8e6e1;
  --muted: #7c828a;
  --accent: #8ea4b8;
  --chroma: #8ea4b8;
  --chroma-dim: #6b8299;
  --chroma-bg: rgba(142,164,184,.08);
  --border: rgba(255,255,255,.06);
  --card-bg: #1a1e24;
  --hover: rgba(142,164,184,.08);
  --reading-bar: #8ea4b8;
}
/* ===== 字体切换 ===== */
:root { --reader-font: "Noto Serif SC","Source Han Serif SC","Songti SC","SimSun","宋体",serif; }
[data-font="kaiti"] { --reader-font: "KaiTi","STKaiti","楷体",serif; }
[data-font="heiti"] { --reader-font: "PingFang SC","Microsoft YaHei","SimHei","黑体",sans-serif; }
.theme-toggle {
  position: fixed;top:1rem;right:1rem;
  background:none;border:1px solid var(--border);cursor:pointer;
  z-index:100;padding:.4rem;line-height:1;border-radius:8px;
  transition:transform .2s;color:var(--text);
}
.theme-toggle:hover{transform:scale(1.15);border-color:var(--chroma);color:var(--chroma)}
#reading-progress{position:fixed;top:0;left:0;height:2px;background:var(--reading-bar);z-index:101;width:0;transition:width .1s linear;border-radius:0 1px 1px 0}
#back-to-top{position:fixed;bottom:1.5rem;right:1.5rem;width:40px;height:40px;border-radius:50%;border:1px solid var(--border);background:var(--bg);color:var(--muted);cursor:pointer;z-index:99;display:flex;align-items:center;justify-content:center;font-size:1.2rem;transition:all .3s;opacity:0;pointer-events:none;transform:translateY(10px)}
#back-to-top.visible{opacity:1;pointer-events:auto;transform:translateY(0)}
#back-to-top:hover{color:var(--chroma);border-color:var(--chroma)}
.icon-yinyang{font-size:1.3rem;line-height:1;display:inline-block;transition:transform .3s}
.icon-yinyang .dot-bg{fill:var(--bg)}
.theme-toggle:hover .icon-yinyang{transform:rotate(180deg)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:18px;line-height:1.8;background:var(--bg)}
body{
  font-family:var(--reader-font),"Noto Sans Runic","Noto Sans Symbols 2",serif;
  background:linear-gradient(135deg,var(--bg),var(--bg2));background-attachment:fixed;
  color:var(--text);
  min-height:100vh;display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;overflow-x:clip;
}
main{flex:1;max-width:var(--max-w);width:100%;margin:0 auto;padding:3rem 1.5rem}
main{animation:fadeIn .4s ease-out}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
h1{font-size:2rem;text-align:center;margin:2.5rem 0 1.5rem;letter-spacing:.08em;font-weight:600}
h2{font-size:1.4rem;margin:2rem 0 .8rem;font-weight:600;color:var(--accent)}
h3{font-size:1.15rem;margin:1.5rem 0 .6rem;font-weight:500;color:var(--chroma)}
h4{font-size:1.05rem;margin:1.2rem 0 .5rem;font-weight:500}
p{margin:0 0 .8em;text-align:justify}
.chapter-content p{text-indent:2em}
	.chapter-content blockquote p,.chapter-content li,.chapter-content li p{text-indent:0}
	.chapter-content ol,.chapter-content ul{padding-left:1.5em}
	.toc-list,.toc-list li{text-indent:0}
a{color:var(--chroma);text-decoration:none;transition:color .2s}
a:hover{color:var(--accent);text-decoration:underline}
code{font-family:"JetBrains Mono","Fira Code",monospace;font-size:.85rem;background:var(--hover);padding:.15em .4em;border-radius:4px;border:1px solid var(--border);color:var(--chroma-dim)}
pre{background:var(--hover);padding:1rem 1.2rem;border-radius:8px;overflow-x:auto;margin:1rem 0;border:1px solid var(--border)}
pre code{background:none;padding:0;font-size:.82rem;line-height:1.6;white-space:pre-wrap;word-break:break-word;border:none;color:inherit}
blockquote{border-left:3px solid var(--chroma);padding:.8rem 1.5rem;margin:1.2rem 0;color:var(--muted);font-style:normal;background:var(--chroma-bg);border-radius:0 6px 6px 0}
ul,ol{margin:.5rem 0 1rem 1.5rem}
li{margin:.3rem 0}
hr{border:none;text-align:center;margin:2.5rem 0;overflow:visible}
hr::after{content:'~  ~  ~';color:var(--chroma-dim);font-size:1rem;letter-spacing:.3em;font-family:serif}
table{border-collapse:collapse;width:100%;margin:1.2rem 0;font-size:.95rem}
th,td{border:1px solid var(--border);padding:.5rem .8rem;text-align:left}
th{background:var(--hover);font-weight:600}
tr:nth-child(even){background:var(--chroma-bg)}
nav{display:flex;align-items:center;gap:1rem}
nav a{font-size:.95rem}
nav .sep{color:var(--muted)}
.top-bar{display:flex;align-items:center;gap:1rem;margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid var(--border);flex-wrap:wrap}
.font-row{display:flex;align-items:center;gap:.5rem}
.font-row .font-btn{background:none;border:none;font-family:inherit;font-size:.9rem;color:var(--muted);cursor:pointer;padding:0 .15rem;transition:color .2s}
.font-row .font-btn:hover{color:var(--text)}
.font-row .font-btn.active{color:var(--accent);font-weight:600}
.toc-list{list-style:none;margin:0;padding:0}
.toc-list li{border-bottom:1px solid var(--border)}
.toc-list a{display:flex;align-items:baseline;padding:.9rem 1rem;font-size:1.1rem;transition:all .15s;border-radius:6px;color:var(--chroma)}
.toc-list a:hover{background:var(--chroma-bg);text-decoration:none;padding-left:1.3rem}
.toc-num{flex-shrink:0;width:2.5rem;color:var(--muted);font-size:.9rem}
.footer{text-align:center;color:var(--muted);font-size:.82rem;padding:2.5rem 0;margin-top:3rem}
.footer p{margin:0}
.chapter-content h2{margin-top:0}
.chapter-nav{display:flex;justify-content:space-between;margin:3rem 0 6rem;padding-top:2rem;border-top:1px solid var(--border)}
.chapter-nav a{font-size:1rem;color:var(--chroma);transition:color .2s}
.chapter-nav a:hover{color:var(--accent);text-decoration:none}
/* ── 首页：居中极简 ── */
.home-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;text-align:center;position:relative}
.cursor-dot{position:fixed;width:5px;height:5px;border-radius:50%;background:var(--accent);opacity:.25;pointer-events:none;z-index:0;filter:blur(1px);animation:drift 28s ease-in-out infinite}
@keyframes drift{0%{top:20%;left:46%}12%{top:17%;left:52%}25%{top:26%;left:49%}37%{top:18%;left:42%}50%{top:24%;left:50%}62%{top:15%;left:47%}75%{top:22%;left:51%}87%{top:19%;left:44%}100%{top:20%;left:46%}}
@media(prefers-reduced-motion){.cursor-dot{animation:none}}
.home-title{font-size:5rem;text-align:center;text-indent:.24em;letter-spacing:.24em;font-weight:700;margin:0;line-height:1.1;position:relative;z-index:1;color:var(--muted)}
.home-sub{font-size:.95rem;color:var(--muted);text-decoration:none;margin-top:.8rem;margin-left:4.5rem;letter-spacing:.08em;transition:color .3s;position:relative;z-index:1}
.home-sub:hover{color:var(--accent)}
.home-nav{display:flex;gap:2.8rem;margin-top:3.2rem;position:relative;z-index:1}
.home-nav a{font-size:1.05rem;color:var(--muted);text-decoration:none;letter-spacing:.12em;transition:color .3s}
.home-nav a:hover{color:var(--accent)}
.home-location{position:fixed;right:1.2rem;bottom:2rem;writing-mode:vertical-rl;font-size:.75rem;color:var(--muted);letter-spacing:.15em;z-index:1;user-select:none;opacity:.55}

/* ── 首页空岛景观（俯瞰线稿） ── */
.sky-arch{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:min(100vw,138vh,1500px);aspect-ratio:3;z-index:0;pointer-events:none}
.sky-arch path,.sky-arch circle{fill:none;stroke:var(--muted);stroke-width:1.1;stroke-linecap:round;stroke-linejoin:round}
.sky-arch .far{opacity:.3}
.sky-arch .mid{opacity:.5}
.sky-arch .front{opacity:.85}
.sky-arch .body,.sky-arch .top{fill:var(--bg)}
.sky-arch .front .body,.sky-arch .front .top{stroke:var(--accent);stroke-width:1.4}
.sky-arch .front .deco{stroke:var(--accent)}
.sky-arch .stars circle{fill:var(--muted);stroke:none}
.isl-a{animation:isl-a 17s ease-in-out infinite}
.isl-b{animation:isl-b 23s ease-in-out infinite}
.isl-c{animation:isl-c 14s ease-in-out infinite}
@keyframes isl-a{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes isl-b{0%,100%{transform:translateY(0)}50%{transform:translateY(5px)}}
@keyframes isl-c{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@media(prefers-reduced-motion){.sky-arch .isl{animation:none}}
@media(max-width:600px){.sky-arch{width:100vw;height:40vh;aspect-ratio:auto}}
@media(min-width:768px){.sky-arch{left:calc(50% + 32px)}}

/* ===== View Transition（主题切换圆盘扩散动画） ===== */
::view-transition-old(root){animation:none}
::view-transition-new(root){animation:none}

/* ===== 宽屏左侧竖栏 ===== */
#side-rail{
  display:none;
  position:fixed;left:0;top:0;bottom:0;width:64px;
  flex-direction:column;align-items:center;padding:1.2rem 0;
  border-right:1px solid var(--border);
  background:var(--bg);z-index:100;
}
.rail-link{
  writing-mode:vertical-rl;letter-spacing:.25em;font-size:.82rem;
  color:var(--muted);text-decoration:none;padding:.4rem .4rem;
  margin:.1rem 0;border-radius:8px;transition:color .2s,background .2s;
}
.rail-link:hover{color:var(--accent);background:var(--hover);text-decoration:none}
.rail-link.cur{color:var(--accent);font-weight:600}
.rail-name{writing-mode:vertical-rl;letter-spacing:.4em;font-size:1.05rem;font-weight:700;color:var(--accent);user-select:none;margin-top:.5rem}
.rail-btn{
  background:none;border:none;cursor:pointer;font-family:inherit;
  color:var(--muted);padding:.45rem .4rem;margin:.15rem 0;
  border-radius:8px;font-size:.82rem;transition:color .2s,background .2s;
  writing-mode:vertical-rl;letter-spacing:.2em;
}
.rail-btn:hover{color:var(--text);background:var(--hover)}
.rail-btn.active{color:var(--accent);font-weight:600}
#railBackTop{margin-top:auto;color:var(--muted);cursor:pointer;background:none;border:none;padding:.4rem;border-radius:8px;font-size:1rem;transition:color .2s,transform .2s;line-height:1}
#railBackTop:hover{color:var(--accent);transform:scale(1.15)}
.rail-spacer{margin-top:auto}
.rail-link.ghost{color:var(--bg);pointer-events:none;cursor:default}
.home-fonts{display:flex;justify-content:center;padding:.6rem 0 0;gap:.3rem}
.home-fonts .font-btn{background:none;border:none;font-family:inherit;font-size:.85rem;color:var(--muted);cursor:pointer;padding:0 .35rem;transition:color .2s;letter-spacing:.08em}
.home-fonts .font-btn:hover{color:var(--accent)}
.home-fonts .font-btn.active{color:var(--accent);font-weight:600}

@media(max-width:600px){html{font-size:16px}main{padding:2rem 1rem}.home-title{font-size:3.2rem}.home-nav{gap:2rem}.chapter-nav{gap:.5rem}}
@media(min-width:768px){
  #side-rail{display:flex}
  .top-bar,.home-fonts{display:none}
  #back-to-top{display:none}
  :root{--max-w:980px}
  main{padding-left:calc(64px + 1.5rem)}
}
"""

PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — 浮生</title>
<link rel="stylesheet" href="{base}style.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
</head>
<body>
<div id="reading-progress"></div>
<div id="side-rail">
  {rail_head}
  <button class="rail-btn font-btn" data-font="songti">宋</button>
  <button class="rail-btn font-btn" data-font="kaiti">楷</button>
  <button class="rail-btn font-btn" data-font="heiti">黑</button>
  {rail_tail}
  <div class="rail-name">浮生</div>
</div>
<button class="theme-toggle" id="themeToggle" title="切换亮色/暗色模式">
<svg class="icon-yinyang" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="11"/><path d="M12 1 A11 11 0 0 0 12 23 A5.5 5.5 0 0 1 12 12 A5.5 5.5 0 0 0 12 1" fill="currentColor" stroke="none"/><circle cx="12" cy="6.5" r="2.2" class="dot-bg" stroke="none"/><circle cx="12" cy="17.5" r="2.2" fill="currentColor" stroke="none"/></svg>
</button>
<main>
{top_bar}
{body}
</main>
{footer}
<button id="back-to-top" title="回到顶部">&uarr;</button>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script src="{base}theme.js"></script>
</body>
</html>"""

THEME_JS = """(function() {
  /* ── 主题切换（View Transition 圆盘扩散动画） ── */
  function getTheme() {
    var saved = localStorage.getItem('theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
  }
  applyTheme(getTheme());

  var toggles = document.querySelectorAll('.theme-toggle');
  for (var i = 0; i < toggles.length; i++) {
    toggles[i].addEventListener('click', function(e) {
      e.stopPropagation();
      var next = getTheme() === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      if (!document.startViewTransition) { applyTheme(next); return; }
      var vt = document.startViewTransition(function() { applyTheme(next); });
      vt.ready.then(function() {
        var x = e.clientX, y = e.clientY;
        var r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
        document.documentElement.animate(
          { clipPath: ['circle(0px at ' + x + 'px ' + y + 'px)', 'circle(' + r + 'px at ' + x + 'px ' + y + 'px)'] },
          { duration: 750, easing: 'cubic-bezier(.22,1,.36,1)', pseudoElement: '::view-transition-new(root)' }
        );
      });
    });
  }

  /* ── 字体切换 ── */
  function getFont() {
    try { return localStorage.getItem('fs-font') || 'songti'; } catch(e) { return 'songti'; }
  }
  function applyFont(f) {
    document.documentElement.setAttribute('data-font', f);
    var btns = document.querySelectorAll('.font-btn');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].dataset.font === f);
    }
  }
  applyFont(getFont());
  var fontBtns = document.querySelectorAll('.font-btn');
  for (var i = 0; i < fontBtns.length; i++) {
    fontBtns[i].addEventListener('click', function() {
      var f = this.dataset.font;
      try { localStorage.setItem('fs-font', f); } catch(e) {}
      applyFont(f);
    });
  }

  /* ── 阅读进度条 ── */
  (function() {
    var bar = document.getElementById('reading-progress');
    if (!bar) return;
    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          var h = document.documentElement.scrollHeight - window.innerHeight;
          bar.style.width = h > 0 ? Math.min((window.scrollY / h) * 100, 100) + '%' : '0%';
          ticking = false;
        });
        ticking = true;
      }
    });
  })();

  /* ── 回到顶部（浮动按钮：窄屏可见） ── */
  (function() {
    var btn = document.getElementById('back-to-top');
    if (!btn) return;
    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          btn.classList.toggle('visible', window.scrollY > 400);
          ticking = false;
        });
        ticking = true;
      }
    });
    btn.addEventListener('click', function() {
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  })();

  /* ── 回到顶部（竖栏按钮：宽屏可见，始终可点） ── */
  (function() {
    var btn = document.getElementById('railBackTop');
    if (!btn) return;
    btn.addEventListener('click', function() {
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  })();

  /* ── 章节导航：用 location.replace 避免返回键在章节间跳转 ── */
  (function() {
    var nav = document.querySelector('.chapter-nav');
    if (!nav) return;
    nav.addEventListener('click', function(e) {
      var a = e.target.closest('a[href]');
      if (!a) return;
      e.preventDefault();
      location.replace(a.getAttribute('href'));
    });
  })();

  /* ── 正文章节目录（chapters.html）：从站外进入时返回键回到首页 ── */
  (function() {
    if (!document.querySelector('.toc-list')) return;
    if (!/chapters\\.html$/.test(location.pathname)) return;
    if (document.referrer && document.referrer.indexOf(location.hostname) !== -1) return;
    history.pushState(null, '', location.href);
    window.addEventListener('popstate', function onPop() {
      window.removeEventListener('popstate', onPop);
      location.replace('index.html');
    });
  })();

  /* ── 设定目录（settings.html）：从站外进入时返回键回到首页 ── */
  (function() {
    if (!document.querySelector('.toc-list')) return;
    if (!/settings\\.html$/.test(location.pathname)) return;
    if (document.referrer && document.referrer.indexOf(location.hostname) !== -1) return;
    history.pushState(null, '', location.href);
    window.addEventListener('popstate', function onPop() {
      window.removeEventListener('popstate', onPop);
      location.replace('index.html');
    });
  })();

  /* ── KaTeX 渲染 ── */
  if (typeof renderMathInElement !== 'undefined') {
    renderMathInElement(document.body, {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false},
      ]
    });
  }
})();"""

CHAPTER_NAV_TPL = """<nav><a href="../chapters.html">← 目录</a><span class="sep">|</span><a href="../index.html">首页</a></nav>"""

SETTING_NAV_TPL = """<nav><a href="../settings.html">← 设定</a><span class="sep">|</span><a href="../index.html">首页</a></nav>"""

LIST_NAV = """<nav><a href="index.html">← 首页</a></nav>"""

# Rail & top-bar fragments
_FONT_BTNS = """<button class="font-btn" data-font="songti">宋体</button>
  <button class="font-btn" data-font="kaiti">楷体</button>
  <button class="font-btn" data-font="heiti">黑体</button>"""
_HOME_FONT_BTNS = """<button class="font-btn" data-font="songti">宋</button>
  <button class="font-btn" data-font="kaiti">楷</button>
  <button class="font-btn" data-font="heiti">黑</button>"""
FONT_ROW = f'<div class="font-row">{_FONT_BTNS}</div>'

RAIL_TAIL_BTN = '<button id="railBackTop" title="回到顶部">&uarr;</button>'
RAIL_TAIL_SPACER = '<span class="rail-spacer"></span>'
RAIL_HEAD_SPACER = '<a class="rail-link ghost">目录</a><a class="rail-link ghost">首页</a>'

def _rail_head(base, toc, *, ghost_toc=False):
    cls = 'rail-link ghost' if ghost_toc else 'rail-link'
    return f'<a class="{cls}" href="{base}{toc}">目录</a><a class="rail-link" href="{base}index.html">首页</a>'

def _top_bar(nav):
    return f'<div class="top-bar">{nav}{FONT_ROW}</div>'

# ── Markdown → HTML ─────────────────────────────────────────

def strip_comments(text):
    """删除 C 风格注释 /* ... */（跨行也支持），顺便吃掉紧邻注释的单空格"""
    text = text.replace(' /*', '/*')
    text = text.replace('*/ ', '*/')
    return re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)


def md_to_html(text):
    return md_lib.markdown(text, extensions=['fenced_code', 'codehilite', 'tables'])


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
            body = strip_comments(body.strip())
            chapters.append({
                'num': ch_num,
                'title': ch_title,
                'body': body,
                'html': md_to_html(body),
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
    """列出 [WLD] Worldbuilding Bureau/ 下所有 .md 文件"""
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

def write_page(rel_path, title, body, base='', *, rail_head='', rail_tail='', top_bar='', footer=''):
    path = DOCS / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        PAGE_TPL.format(title=title, base=base, body=body, rail_head=rail_head, rail_tail=rail_tail, top_bar=top_bar, footer=footer),
        encoding='utf-8'
    )


def _home_sky_svg():
    """生成首页底部的空岛界线稿（高空俯瞰视角，可见上表面）。

    每座空岛 = 边缘微扭曲的类椭圆上表面 + 下方岛身（尖底或平底）。
    用固定种子的随机扰动让每座岛形态各异。
    """
    rng = random  # 不固定种子，每次构建形态略有不同

    def blob(cx, cy, rx, ry, n=10):
        """过 10 个 jitter 锚点的 Catmull-Rom → Cubic Bézier 闭合平滑曲线。返回 (path, 锚点列表)。"""
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            f = 1 + rng.uniform(-0.08, 0.08)
            pts.append((cx + math.cos(a) * rx * f, cy + math.sin(a) * ry * f))
        d_parts = []
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            prev = pts[(i - 1) % n]
            nxt = pts[(i + 2) % n]
            # Catmull-Rom 切线 → 三次贝塞尔控制点
            cp1 = (p0[0] + (p1[0] - prev[0]) / 6, p0[1] + (p1[1] - prev[1]) / 6)
            cp2 = (p1[0] - (nxt[0] - p0[0]) / 6, p1[1] - (nxt[1] - p0[1]) / 6)
            if i == 0:
                d_parts.append(f'M{p0[0]:.0f},{p0[1]:.0f}')
            d_parts.append(f'C{cp1[0]:.0f},{cp1[1]:.0f} {cp2[0]:.0f},{cp2[1]:.0f} {p1[0]:.0f},{p1[1]:.0f}')
        return ' '.join(d_parts) + ' Z', pts

    def island_body(cx, cy, rx, d, flat, lx, rx_):
        """岛身：从上表面左右锚点垂下，尖底或平底。开放路径，填充时自动闭合成弦（被上表面遮住）"""
        if flat:
            return (f'M{lx:.0f},{cy} C{lx - 3:.0f},{cy + d * 0.4:.0f} {cx - rx * 0.85:.0f},{cy + d * 0.8:.0f} {cx - rx * 0.62:.0f},{cy + d:.0f}'
                    f' C{cx - rx * 0.2:.0f},{cy + d * 1.1:.0f} {cx + rx * 0.3:.0f},{cy + d * 0.88:.0f} {cx + rx * 0.58:.0f},{cy + d * 0.94:.0f}'
                    f' C{cx + rx * 0.82:.0f},{cy + d * 0.72:.0f} {rx_ + 3:.0f},{cy + d * 0.38:.0f} {rx_:.0f},{cy}')
        tip = cx + rng.uniform(-0.15, 0.05) * rx
        return (f'M{lx:.0f},{cy} C{lx - 2:.0f},{cy + d * 0.32:.0f} {cx - rx * 0.48:.0f},{cy + d * 0.66:.0f} {tip:.0f},{cy + d:.0f}'
                f' C{cx + rx * 0.5:.0f},{cy + d * 0.62:.0f} {rx_ + 2:.0f},{cy + d * 0.3:.0f} {rx_:.0f},{cy}')

    def trees(cx, cy, rx, ry):
        spots = ((-0.28, -0.05), (0.22, 0.18))
        trunks = ' '.join(f'M{cx + rx * fx:.0f},{cy + ry * fy:.0f} L{cx + rx * fx:.0f},{cy + ry * fy - 7:.0f}' for fx, fy in spots)
        crowns = ''.join(f'<circle class="deco" cx="{cx + rx * fx:.0f}" cy="{cy + ry * fy - 9:.0f}" r="2.2"/>' for fx, fy in spots)
        return f'<path class="deco" d="{trunks}"/>' + crowns

    # (cx, cy, 半径rx, 岛身深度, 是否平底, 层, 浮动动画, 表面装饰)
    ISLANDS = [
        (150, 150, 46, 55, False, 'far', 'b', None),
        (420, 105, 38, 48, True, 'far', 'a', None),
        (700, 160, 52, 70, False, 'far', 'c', None),
        (1010, 120, 42, 50, False, 'far', 'b', None),
        (1300, 185, 48, 42, True, 'far', 'a', None),
        (300, 260, 66, 85, False, 'mid', 'c', None),
        (620, 305, 58, 60, True, 'mid', 'b', None),
        (880, 265, 68, 110, False, 'mid', 'a', 'pond'),
        (1180, 315, 62, 70, True, 'mid', 'c', None),
        (480, 390, 92, 85, False, 'front', 'a', None),
        (840, 395, 80, 70, True, 'front', 'c', None),
        (1150, 390, 88, 88, False, 'front', 'b', None),
    ]
    layers = {'far': [], 'mid': [], 'front': []}
    for cx, cy, rx, d, flat, layer, anim, deco in ISLANDS:
        ry = rx * 0.38
        top_d, pts = blob(cx, cy, rx, ry)
        body_d = island_body(cx, cy, rx, d, flat, pts[5][0], pts[0][0])
        parts = [f'<path class="body" d="{body_d}"/>', f'<path class="top" d="{top_d}"/>']
        if deco == 'trees':
            parts.append(trees(cx, cy, rx, ry))
        elif deco == 'pond':
            pond_d, _ = blob(cx + rx * 0.15, cy + ry * 0.1, rx * 0.28, ry * 0.32, n=7)
            parts.append(f'<path class="deco" d="{pond_d}"/>')
        layers[layer].append(f'<g class="isl isl-{anim}">' + ''.join(parts) + '</g>')

    return ('<svg class="sky-arch" viewBox="0 0 1440 480" preserveAspectRatio="xMidYMax slice" aria-hidden="true">'
            '<g class="far">'
            '<g class="stars">'
            '<circle cx="180" cy="48" r="1.6"/><circle cx="560" cy="36" r="1.3"/>'
            '<circle cx="860" cy="66" r="1.5"/><circle cx="1020" cy="28" r="1.3"/>'
            '<circle cx="1340" cy="104" r="1.4"/></g>'
            + ''.join(layers['far']) + '</g>'
            '<g class="mid">' + ''.join(layers['mid']) + '</g>'
            '<g class="front">' + ''.join(layers['front']) + '</g>'
            '</svg>')


def build():
    DOCS.mkdir(exist_ok=True)

    # 写出共享的 CSS 和 JS 文件
    (DOCS / 'style.css').write_text(CSS, encoding='utf-8')
    (DOCS / 'theme.js').write_text(THEME_JS, encoding='utf-8')

    # 1. 解析数据
    chapters, novel_title = parse_chapters()
    settings = parse_settings()

    # 2. 首页 — 居中极简布局
    sky = _home_sky_svg()
    body = f'''<div class="home-wrap">
  <div class="cursor-dot" aria-hidden="true"></div>
  <h1 class="home-title">{novel_title}</h1>
  <a class="home-sub" href="https://space.bilibili.com/1410666014" target="_blank" rel="noopener">——律</a>
  <nav class="home-nav">
    <a href="chapters.html">正文</a>
    <a href="settings.html">设定</a>
  </nav>
  <div class="home-fonts">{_HOME_FONT_BTNS}</div>
  {sky}
  <div class="home-location">因南岛群西部边缘一隅</div>
</div>'''
    write_page('index.html', '首页', body, base='',
               rail_head=RAIL_HEAD_SPACER, rail_tail=RAIL_TAIL_SPACER, footer='',
               top_bar='')

    # 3. 章节目录页
    toc_items = []
    for ch in chapters:
        toc_items.append(
            f'<li><a href="chapter/{ch["num"]}.html">'
            f'<span class="toc-num">{ch["num"]}</span>{ch["title"]}'
            f'</a></li>'
        )
    body = f'<h1>浮生</h1>\n<ul class="toc-list">\n' + '\n'.join(toc_items) + '\n</ul>'
    write_page('chapters.html', '浮生', body, base='',
               rail_head=_rail_head('', 'chapters.html', ghost_toc=True),
               rail_tail=RAIL_TAIL_BTN,
               top_bar=_top_bar(LIST_NAV))

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
        write_page(f'chapter/{ch["num"]}.html', f'{ch["num"]} {ch["title"]}', body, base='../',
                   rail_head=_rail_head('../', 'chapters.html'),
                   rail_tail=RAIL_TAIL_BTN,
                   top_bar=_top_bar(CHAPTER_NAV_TPL))

    # 5. 设定集列表页
    setting_items = []
    for s in settings:
        setting_items.append(
            f'<li><a href="setting/{s["slug"]}.html">'
            f'<span class="toc-num">{s["num"]}</span>{s["title"]}'
            f'</a></li>'
        )
    body = f'<h1>设定</h1>\n<ul class="toc-list">\n' + '\n'.join(setting_items) + '\n</ul>'
    write_page('settings.html', '设定', body, base='',
               rail_head=_rail_head('', 'settings.html', ghost_toc=True),
               rail_tail=RAIL_TAIL_BTN,
               top_bar=_top_bar(LIST_NAV))

    # 6. 各设定文档页
    for s in settings:
        raw = Path(s['path']).read_text(encoding='utf-8-sig').lstrip('﻿')
        # 去掉首行 # 标题（页面用 h2 显示）
        lines = raw.split('\n', 1)
        content = lines[1].strip() if len(lines) > 1 else raw
        content = strip_comments(content)
        html = md_to_html(content)
        body = f'<h2>{s["title"]}</h2>\n<div class="chapter-content">\n{html}\n</div>'
        write_page(f'setting/{s["slug"]}.html', s['title'], body, base='../',
                   rail_head=_rail_head('../', 'settings.html'),
                   rail_tail=RAIL_TAIL_BTN,
                   top_bar=_top_bar(SETTING_NAV_TPL))

    # 7. 复制静态字体文件
    fonts_src = BASE / "static" / "fonts"
    fonts_dst = DOCS / "fonts"
    if fonts_src.is_dir():
        if fonts_dst.exists():
            shutil.rmtree(fonts_dst)
        shutil.copytree(fonts_src, fonts_dst)

    print(f'[OK] Generated {len(chapters)} chapters + {len(settings)} settings docs')
    print(f'  Home: docs/index.html')
    print(f'  TOC:  docs/chapters.html')
    print(f'  Settings: docs/settings.html')


if __name__ == '__main__':
    build()
