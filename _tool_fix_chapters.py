"""
整理 Markdown 正文的章节序号（`## N 标题` / `## 标题`）。

检测以 `## ` 开头的章节标题，按出现顺序重排为连续序号；
先打印报告，经用户输入 y 确认后，再备份并写回。

分节规则：每个 `# ` 标题视作分节符，会打断章节序列；每个分节内的章节独立编号。
分节内起始序号规则：该分节第一个章节标题若有数字序号，则沿用该序号作起点；否则从 0 开始。
换行符（CRLF / LF）原样保留，不做转换。

用法：
    python _tool_fix_chapters.py "浮生 · 满梧.md"   # 处理指定文件（可多个）
"""
import os
import re
import shutil
import sys
import time

import _lib.toolignore as toolignore


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


def process_file(filepath):
    """检测并整理单个文件的章节序号。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    headers, h1s = parse_headers(lines)

    if not headers:
        print(f"[{filepath}] 未检测到章节标题，跳过。")
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
    if not changed:
        print(f"[{filepath}] 检测到 {len(headers)} 个章节标题、{len(h1s)} 个分节，序号已连续，无需修改。")
        return

    print(f"\n[{filepath}] 检测到 {len(headers)} 个章节标题、{len(h1s)} 个分节：\n")
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

    renum = sum(1 for h in changed if h['old'] is not None)
    fill = sum(1 for h in changed if h['old'] is None)
    print(f"\n共 {len(headers)} 个章节，{renum} 处重编、{fill} 处补号。")

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

    print(f"[{filepath}] 已写入，共修改 {len(changed)} 处序号。")


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
