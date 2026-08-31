"""
整理 Markdown 正文的章节序号（`## N 标题` / `## 标题`）。

检测以 `## ` 开头的章节标题，按出现顺序重排为连续序号；
先打印报告，经用户输入 y 确认后，再备份并写回。

分节规则：每个 `# ` 标题视作分节符，会打断章节序列；每个分节内的章节独立编号。
分节内起始序号规则：该分节第一个章节标题若有数字序号，则沿用该序号作起点；否则从 0 开始。
换行符（CRLF / LF）原样保留，不做转换。

### 标题标签（仅文件名含 `_toWrite` 时启用）：
`### 标题_标签1_标签2`。特殊标签两类：
- 时间标签 `time0`、`time1`… 排在一行最前（一个标题可有多个，排序以最大值为准）；
- 状态标签（`丢弃`、`完成`，可扩展）排在末尾。

除规范化标签位置外，还会对 `###` 文块排序：无状态 → 丢弃 → 完成；
组内无时间标签置顶，时间按无状态升序、有状态降序。排序不跨 `#`/`##` 分节。
（标题文字中请勿使用 `_`。）

用法：
    python _tool_fix_chapters.py "浮生 · 满梧.md"   # 处理指定文件（可多个）
"""
import os
import re
import shutil
import sys
import time

import _lib.toolignore as toolignore

# —— ### 标题标签（仅文件名含 _toWrite 时启用）——
STATUS_TAGS = ['丢弃', '完成']         # 有序状态标签，可追加
TIME_RE = re.compile(r'^time\d+$')     # time0, time1, ...（非负整数）


def parse_headers(lines):
    """逐行识别章节标题（列 0 的 '## '）与分节标题（列 0 的 '# '），跳过 fenced 代码块内部。

    返回 (headers, h1s)：
        headers 列表，每项为 dict：{idx, old, title}
        h1s 列表，每项为 dict：{idx, title}
    """
    headers = []
    h1s = []
    in_codeblock = False
    for idx, raw in enumerate(lines):
        s = raw.rstrip('\r\n')
        if s.startswith('```') or s.startswith('~~~'):
            in_codeblock = not in_codeblock
            continue
        if in_codeblock:
            continue
        if s.startswith('## '):
            m = re.match(r'^## (\d+) (.*)$', s)
            if m:
                headers.append({'idx': idx, 'old': int(m.group(1)), 'title': m.group(2)})
            else:
                rest = s[3:].strip()
                if rest and not rest.startswith('#'):
                    headers.append({'idx': idx, 'old': None, 'title': rest})
        elif s.startswith('# '):
            title = s[2:].strip()
            if title:
                h1s.append({'idx': idx, 'title': title})
    return headers, h1s


def parse_h3_heading(line):
    """解析 '### 标题_tag1_tag2' → (title, [tags])；无 _ 则 tags 为空。"""
    s = line.rstrip('\r\n')
    content = s[4:] if s.startswith('### ') else s
    title, _, tagstr = content.partition('_')
    if not tagstr:
        return title.strip(), []
    return title.strip(), [t for t in tagstr.split('_') if t]


def status_of(tags):
    """返回状态标签在 STATUS_TAGS 中的下标；无则 -1。"""
    for t in tags:
        if t in STATUS_TAGS:
            return STATUS_TAGS.index(t)
    return -1


def time_of(tags):
    """返回时间标签的最大数值（int）；无则 None。"""
    vals = [int(t[4:]) for t in tags if TIME_RE.match(t)]
    return max(vals) if vals else None


def normalize_h3_heading(line):
    """重排 '### 标题_tags' 为 标题 + time(升序) + 其他(原序) + 状态(STATUS_TAGS 序)。"""
    stripped = line.rstrip('\r\n')
    line_ending = line[len(stripped):]
    title, tags = parse_h3_heading(line)
    if not tags:
        return line
    times = sorted((t for t in tags if TIME_RE.match(t)), key=lambda t: int(t[4:]))
    statuses = sorted((t for t in tags if t in STATUS_TAGS), key=STATUS_TAGS.index)
    others = [t for t in tags if not TIME_RE.match(t) and t not in STATUS_TAGS]
    ordered = times + others + statuses
    return '### ' + title + ''.join('_' + t for t in ordered) + line_ending


def block_sort_key(block):
    """排序键：状态分组（无状态→丢弃→完成），组内无时间标签置顶，再按时间（无状态升序 / 有状态降序）。"""
    status = block['status']
    time = block['time']
    if status == -1:
        return (0, 0 if time is None else 1, time if time is not None else 0)
    return (status + 1, 0 if time is None else 1, -(time if time is not None else 0))


def apply_h3_tag_logic(lines):
    """处理 _toWrite 的 ### 标签规范化与排序（仅文件名含 _toWrite 时调用）。

    返回 (new_lines, tag_norm, sort_reports)：
        new_lines     重排后的行列表（保留行尾）
        tag_norm      [(旧标题行, 新标题行), ...] 标签规范化记录
        sort_reports  [{'section', 'old': [标题], 'new': [标题]}, ...]
    """
    n = len(lines)
    is_head = [False] * n
    level = [0] * n
    in_codeblock = False
    for i, raw in enumerate(lines):
        s = raw.rstrip('\r\n')
        if s.startswith('```') or s.startswith('~~~'):
            in_codeblock = not in_codeblock
            continue
        if in_codeblock:
            continue
        if s.startswith('### '):
            is_head[i] = True; level[i] = 3
        elif s.startswith('## '):
            is_head[i] = True; level[i] = 2
        elif s.startswith('# '):
            is_head[i] = True; level[i] = 1

    blocks = []
    group = 0
    section = ''
    current = None
    pending = []          # 空行（line 字符串），若下一行是标题则作为该块的前导
    in_codeblock = False
    for i in range(n):
        s = lines[i].rstrip('\r\n')
        if s.startswith('```') or s.startswith('~~~'):
            in_codeblock = not in_codeblock
        if is_head[i]:
            if level[i] <= 2:
                group += 1
                section = s[level[i] + 1:].strip()
            if level[i] == 3:
                # 前导空行单独存 lead，避免占掉 lines[0]（标题行）
                current = {'kind': 'h3', 'lines': [lines[i]], 'lead': pending, 'group': group, 'section': section}
            else:
                current = {'kind': 'text', 'lines': pending + [lines[i]]}
            blocks.append(current)
            pending = []
        elif not in_codeblock and lines[i].strip() == '':
            pending.append(lines[i])
        else:
            if pending:
                # 空行在正文中间 → 归入当前块正文
                if current is None:
                    current = {'kind': 'text', 'lines': []}
                    blocks.append(current)
                current['lines'].extend(pending)
                pending = []
            if current is None:
                current = {'kind': 'text', 'lines': [lines[i]]}
                blocks.append(current)
            else:
                current['lines'].append(lines[i])
    if pending:            # 文件末尾残留的空行，保留在原位
        if current is None:
            current = {'kind': 'text', 'lines': []}
            blocks.append(current)
        current['lines'].extend(pending)

    # 标签规范化
    tag_norm = []
    for b in blocks:
        if b['kind'] != 'h3':
            continue
        old_line = b['lines'][0]
        new_line = normalize_h3_heading(old_line)
        if new_line != old_line:
            tag_norm.append((old_line, new_line))
            b['lines'][0] = new_line
        title, tags = parse_h3_heading(new_line)
        b['title'] = title
        b['status'] = status_of(tags)
        b['time'] = time_of(tags)

    # 找连续的、同 group 的 h3 序列（run）
    runs = []
    bcount = len(blocks)
    i = 0
    while i < bcount:
        if blocks[i]['kind'] != 'h3':
            i += 1
            continue
        j = i
        while j + 1 < bcount and blocks[j + 1]['kind'] == 'h3' and blocks[j + 1]['group'] == blocks[j]['group']:
            j += 1
        run = blocks[i:j + 1]
        keyed = sorted(range(len(run)), key=lambda k: block_sort_key(run[k]))
        runs.append({'start': i, 'end': j + 1, 'keyed': keyed})
        i = j + 1

    # 排序报告 + 重组
    sort_reports = []
    for r in runs:
        start, end, keyed = r['start'], r['end'], r['keyed']
        if keyed == list(range(end - start)):
            continue
        old_titles = [blocks[start + k]['title'] for k in range(end - start)]
        new_titles = [blocks[start + k]['title'] for k in keyed]
        sort_reports.append({'section': blocks[start]['section'], 'old': old_titles, 'new': new_titles})

    new_lines = []
    b_idx = 0
    for r in runs:
        start, end, keyed = r['start'], r['end'], r['keyed']
        while b_idx < start:
            new_lines.extend(blocks[b_idx]['lines']); b_idx += 1
        for k in keyed:
            b = blocks[start + k]
            new_lines.extend(b.get('lead', []) + b['lines'])
        b_idx = end
    while b_idx < bcount:
        new_lines.extend(blocks[b_idx]['lines']); b_idx += 1

    return new_lines, tag_norm, sort_reports


def process_file(filepath):
    """检测并整理单个文件的章节序号；文件名含 _toWrite 时额外处理 ### 标签与排序。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        content = f.read()

    lines = content.splitlines(keepends=True)

    tag_norm = []
    sort_reports = []
    if '_toWrite' in os.path.basename(filepath):
        lines, tag_norm, sort_reports = apply_h3_tag_logic(lines)

    headers, h1s = parse_headers(lines)

    if not headers and not tag_norm and not sort_reports:
        print(f"[{filepath}] 未检测到章节标题或 ### 标签改动，跳过。")
        return

    # 分节编号：每个 # 标题视作分节符，打断章节序列；分节内重新编号。
    current_section = -1
    for h in headers:
        sec = sum(1 for x in h1s if x['idx'] < h['idx'])
        if sec != current_section:
            current_section = sec
            start = h['old'] if h['old'] is not None else 0
        h['new'] = start
        start += 1

    changed = [h for h in headers if h['old'] != h['new']]
    if not changed and not tag_norm and not sort_reports:
        print(f"[{filepath}] 检测到 {len(headers)} 个章节标题、{len(h1s)} 个分节，序号与标签均已就绪，无需修改。")
        return

    print(f"\n[{filepath}] 检测到 {len(headers)} 个章节标题、{len(h1s)} 个分节：\n")

    if headers:
        current_section = -1
        for h in headers:
            sec = sum(1 for x in h1s if x['idx'] < h['idx'])
            if sec != current_section:
                current_section = sec
                if current_section >= 1:
                    print(f"  ── # {h1s[current_section - 1]['title']} ──")
                else:
                    print("  ──（正文起始分节）──")
            old_disp = str(h['old']) if h['old'] is not None else '（无）'
            if h['old'] is None:
                kind = '补号'
            elif h['old'] == h['new']:
                kind = '不变'
            else:
                kind = '重编'
            print(f"  [{kind}]  {old_disp} → {h['new']}  {h['title']}")

    if tag_norm:
        print("\n── ### 标签规范化 ──")
        for old, new in tag_norm:
            print(f"  {old.rstrip()}  →  {new.rstrip()}")

    if sort_reports:
        print("\n── ### 排序 ──")
        for r in sort_reports:
            print(f"  [{r['section']}]")
            print(f"    旧: {' | '.join(r['old'])}")
            print(f"    新: {' | '.join(r['new'])}")

    renum = sum(1 for h in changed if h['old'] is not None)
    fill = sum(1 for h in changed if h['old'] is None)
    print(f"\n共 {len(headers)} 个章节，{renum} 处重编、{fill} 处补号；"
          f"### 标签规范化 {len(tag_norm)} 处、排序 {len(sort_reports)} 组。")

    try:
        answer = input("是否写入修改？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return

    if answer not in ('y', 'yes'):
        print("已取消。")
        return

    stem, ext = os.path.splitext(filepath)
    backup_path = stem + '_Original' + ext
    shutil.copy2(filepath, backup_path)
    print(f"[{filepath}] 备份已保存：{backup_path}")

    for h in headers:
        raw = lines[h['idx']]
        stripped = raw.rstrip('\r\n')
        line_ending = raw[len(stripped):]
        lines[h['idx']] = f'## {h["new"]} {h["title"]}{line_ending}'

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(lines))

    total = len(changed) + len(tag_norm) + len(sort_reports)
    print(f"[{filepath}] 已写入，共修改 {total} 处。")


def main():
    files = sys.argv[1:]
    if not files:
        print("未指定文件。")
        print('用法：python _tool_fix_chapters.py "浮生 · 满梧.md" [更多文件...]')
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
