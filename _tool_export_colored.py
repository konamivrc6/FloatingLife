"""
生成带高亮颜色的 Markdown 副本，供 markdown-pdf 导出 PDF / HTML 用。

编辑器的 floatinglife-markdown-highlight 用的是 VS Code 装饰（decoration），颜色只活在编辑器
里、不落盘，markdown-pdf 导出时看不到。本脚本把匹配到的子串包成
`<span style="color:…">…</span>`：markdown-pdf 的管线是
markdown-it(html:true) → sanitizeRawHtml → Chromium，原生 HTML 原样透传，而它的 sanitizer
（默认 sanitize:"gfm"）只移除 script/style/iframe 等固定标签、只剥掉 on* 与 javascript:，
`<span style>` 完整保留，颜色于是能进 PDF。这也是唯一可行路径——markdown-pdf 没有
markdown-it 插件钩子，而 markdown-pdf.styles 是纯 CSS，无法对正则子串上色。

每个 X.md 在同目录生成 X_colored.md（原文件只读，不改动）：用 VS Code 打开副本，执行
`Markdown PDF: Export (pdf)` 即可。副本是派生文件，`*_colored*` 已同时写进 .gitignore 与
.toolignore——不进 git，也不会被 build.py 或其它读忽略规则的工具扫到（_tool_strip_bom.py
不读 .toolignore，但它只会无害地去掉 BOM）。

规则表与 extensions/floatinglife-markdown-highlight/main.js 的 RULES 同步，有两处刻意差异：
1. 去掉引号/书名号（“ ” 「 」 《 》）那条——正文约 630 处对话，全染橙过于醒目；
2. 时间标签的编辑器色 #E5C07B 是为深色主题挑的，在白纸上看不清，改用打印适配的深金 #B8860B。
时间标签正则与 _tool_fix_chapters.py 的 TIME_RE 一致（time0 / time0.5 / time-1 …）。

区域内原文做 HTML 转义（& < >），免得注释里的尖括号被 markdown-it 当成标签吞掉；区域外一字
不改——正文里有 <u>…</u>、<br/> 这类原生 HTML，必须原样留给 markdown-it。换行符统一为 LF
（读取后删除所有 \r）；BOM 不保留（读取时以 utf-8-sig 剥离）。

用法：
    python _tool_export_colored.py "浮生 · 满梧.md" ["浮生 · 满梧_toWrite.md" ...]
"""
import os
import re
import sys
import time

import _lib.toolignore as toolignore

# —— 高亮规则（镜像 main.js 的 RULES；见文件头说明）——
H3_TAG_RE = re.compile(r'^### .*?(_[^\n]*)$', re.M)   # 组 1 = 从第一个 `_` 起的标签区
TIME_TAG_RE = re.compile(r'^time-?\d+(?:\.\d+)?$')    # 与 _tool_fix_chapters.py 的 TIME_RE 一致

# (名称, 正则, 颜色, 选择器)
# 选择器 'whole' = 整段染色；'tag:<kind>' = 只染标签区里的那一类 token
RULES = [
    ('块注释', re.compile(r'/\*[\s\S]*?\*/'), '#4caf50', 'whole'),
    ('时间标签', H3_TAG_RE, '#B8860B', 'tag:time'),     # 编辑器是 #E5C07B，纸面改用深金
    ('丢弃标签', H3_TAG_RE, '#E05561', 'tag:discard'),
    ('完成标签', H3_TAG_RE, '#4CAF50', 'tag:done'),
    ('其他标签', H3_TAG_RE, '#808080', 'tag:other'),
]

_ESCAPES = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))


def escape_html(s):
    """HTML 转义。顺序不能变：& 必须先处理，否则会把刚生成的实体二次转义。"""
    for char, entity in _ESCAPES:
        s = s.replace(char, entity)
    return s


def tag_spans(match, kind):
    """把 H3_TAG_RE 匹配出的标签区按 kind 拆成若干 (start, end)。

    等价于 main.js 的 tagPairs：`_` 与「杂项标签」同归 other；时间标签含小数/负数（见
    TIME_TAG_RE），其余非空 token 一律算 other。不为该 kind 时返回空列表。
    """
    region = match.group(1)          # 以 `_` 开头
    base = match.start(1)
    spans = []
    i = 0
    while i < len(region):
        if region[i] == '_':
            if kind == 'other':
                spans.append((base + i, base + i + 1))
            i += 1
            continue
        start = i
        while i < len(region) and region[i] != '_':
            i += 1
        token = region[start:i]
        if token == '丢弃':
            actual = 'discard'
        elif token == '完成':
            actual = 'done'
        elif TIME_TAG_RE.match(token):
            actual = 'time'
        else:
            actual = 'other'
        if actual == kind:
            spans.append((base + start, base + i))
    return spans


def collect_spans(text):
    """扫描全文，返回 [(start, end, color, name), ...]，按 start 升序。"""
    spans = []
    for name, regex, color, selector in RULES:
        for match in regex.finditer(text):
            if selector == 'whole':
                spans.append((match.start(), match.end(), color, name))
            else:
                kind = selector.split(':', 1)[1]
                for start, end in tag_spans(match, kind):
                    spans.append((start, end, color, name))
    spans.sort(key=lambda span: (span[0], span[1]))
    return spans


def wrap(text, spans):
    """按边界插入 <span>，返回 (新文本, 实际染色区间数)。

    区域内原文转义，区域外一字不改。区间重叠时跳过靠后的一条并告警——正常规则表下不会
    发生，出现即说明规则有 bug，宁可留白也不要拼出交叉的标签。
    """
    out = []
    cursor = 0
    used = 0
    for start, end, color, name in spans:
        if start < cursor:
            print(f"  警告：{name} 区间 [{start}, {end}) 与前一处重叠，已跳过：{text[start:end]!r}",
                  file=sys.stderr)
            continue
        out.append(text[cursor:start])
        out.append(f'<span style="color:{color}">')
        out.append(escape_html(text[start:end]))
        out.append('</span>')
        cursor = end
        used += 1
    out.append(text[cursor:])
    return ''.join(out), used


def process_file(filepath):
    """处理单个文件：扫描 → 生成 <名>_colored 副本。原文件只读，不改动。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        content = f.read()
    content = content.replace('\r', '')   # 统一 LF

    spans = collect_spans(content)
    if not spans:
        print(f"[{filepath}] 未检测到可染色内容，跳过。")
        return

    result, used = wrap(content, spans)

    stem, ext = os.path.splitext(filepath)
    out_path = stem + '_colored' + ext
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(result)

    counts = {}
    for _start, _end, _color, name in spans:
        counts[name] = counts.get(name, 0) + 1
    detail = '、'.join(f'{name} {count}' for name, count in counts.items())
    print(f"[{filepath}] → {out_path}：染色 {used} 处（{detail}）")


def main():
    files = sys.argv[1:]
    if not files:
        print("未指定文件。")
        print('用法：python _tool_export_colored.py "浮生 · 满梧.md" [更多文件...]')
        time.sleep(0.5)
        sys.exit(1)

    for filepath in files:
        if toolignore.is_ignored(os.path.basename(filepath)):
            print(f"[{filepath}] 命中忽略规则，跳过。")
            continue
        process_file(filepath)

    print("All files processed.")
    time.sleep(0.5)
    sys.exit(0)


if __name__ == "__main__":
    main()
