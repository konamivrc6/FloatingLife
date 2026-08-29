"""
整理 Markdown 正文的章节序号（`## N 标题` / `## 标题`）。

检测以 `## ` 开头的章节标题，按出现顺序重排为连续序号；
先打印报告，经用户输入 y 确认后，再备份并写回。

起始序号规则：第一个章节标题若有数字序号，则沿用该序号作起点；否则从 0 开始。
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
    """逐行识别章节标题（列 0 的 '## '），跳过 fenced 代码块内部。

    返回 headers 列表，每项为 dict：
        {idx: 行索引, old: 原序号(int) 或 None, title: 标题文字}
    """
    headers = []
    in_codeblock = False
    for idx, raw in enumerate(lines):
        s = raw.rstrip('\r\n')
        if s.startswith('```') or s.startswith('~~~'):
            in_codeblock = not in_codeblock
            continue
        if in_codeblock:
            continue
        if not s.startswith('## '):
            continue
        m = re.match(r'^## (\d+) (.*)$', s)
        if m:
            headers.append({'idx': idx, 'old': int(m.group(1)), 'title': m.group(2)})
        else:
            rest = s[3:].strip()
            if rest and not rest.startswith('#'):
                headers.append({'idx': idx, 'old': None, 'title': rest})
    return headers


def process_file(filepath):
    """检测并整理单个文件的章节序号。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    headers = parse_headers(lines)

    if not headers:
        print(f"[{filepath}] 未检测到章节标题，跳过。")
        return

    start = headers[0]['old'] if headers[0]['old'] is not None else 0

    for i, h in enumerate(headers):
        h['new'] = start + i

    changed = [h for h in headers if h['old'] != h['new']]
    if not changed:
        print(f"[{filepath}] 检测到 {len(headers)} 个章节标题（起始序号 {start}），序号已连续，无需修改。")
        return

    print(f"\n[{filepath}] 检测到 {len(headers)} 个章节标题，起始序号 {start}：\n")
    for h in headers:
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
