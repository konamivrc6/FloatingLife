import sys
import re
import time
import shutil
import os

def replace_outside_codeblocks(content, pattern, replacement):
    """仅在fenced代码块(```...```)外部执行正则替换。"""
    parts = re.split(r'(```[\s\S]*?```)', content)
    result_parts = []
    for i, part in enumerate(parts):
        # 偶数索引：代码块外部 → 执行替换
        # 奇数索引：代码块内部 → 保持原样
        if i % 2 == 0:
            result_parts.append(re.sub(pattern, replacement, part))
        else:
            result_parts.append(part)
    return ''.join(result_parts)


def _replace_dashes_callback(match):
    """替换4个及以上连续-为——，但跳过表格分隔线。
    若该段-的前一个字符和后一个字符都属于 : 或 |，则不替换。"""
    start = match.start()
    end = match.end()
    text = match.string

    prev_char = text[start - 1] if start > 0 else ''
    next_char = text[end] if end < len(text) else ''

    if prev_char in ':|' and next_char in ':|':
        return match.group(0)
    return '——'


def replace_dashes_outside_codeblocks(content):
    """仅在代码块外部将4个及以上连续-替换为——，跳过表格分隔线。"""
    parts = re.split(r'(```[\s\S]*?```)', content)
    result_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            result_parts.append(re.sub(r'-{4,}', _replace_dashes_callback, part))
        else:
            result_parts.append(part)
    return ''.join(result_parts)


def process_file(filepath):
    """处理单个 Markdown 文件：备份 → 标准化 → 写回。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    # 构造备份文件名
    base, ext = os.path.splitext(filepath)
    backup_path = base + "_Original" + ext

    # 复制原文件内容到备份（覆盖已有同名文件）
    shutil.copy2(filepath, backup_path)
    print(f"[{filepath}] Backup saved as: {backup_path}")

    # 读取原文件内容
    with open(filepath, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    def process_paired_markers(text, marker, open_replacement, close_replacement, skip_when_ascii_adjacent=False, no_cross_newline=False):
        """处理成对标记，奇数次出现替换为 open_replacement，偶数次替换为 close_replacement。
        当 skip_when_ascii_adjacent=True 时，若标记前或后有 ASCII 字母/数字相邻，则不替换该标记，避免误改英文内容。
        当 no_cross_newline=True 时，若当前标记与下一个匹配标记之间包含换行符，则不替换该标记，避免跨行配对。"""
        result = []
        is_open = True
        i = 0
        marker_len = len(marker)
        while i < len(text):
            if text[i:i+marker_len] == marker:
                if skip_when_ascii_adjacent:
                    prev_char = text[i-1] if i > 0 else ''
                    next_char = text[i+marker_len] if i + marker_len < len(text) else ''
                    if (prev_char and re.match(r'[a-zA-Z0-9]', prev_char)) or \
                       (next_char and re.match(r'[a-zA-Z0-9]', next_char)):
                        result.append(marker)
                        i += marker_len
                        continue
                if no_cross_newline and is_open:
                    next_pos = text.find(marker, i + marker_len)
                    if next_pos != -1 and '\n' in text[i + marker_len:next_pos]:
                        result.append(marker)
                        i += marker_len
                        result.append(text[i:next_pos + marker_len])
                        i = next_pos + marker_len
                        continue
                result.append(open_replacement if is_open else close_replacement)
                is_open = not is_open
                i += marker_len
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    # 步骤0：删除所有 <br/>、\r 和零宽空格
    content = re.sub(r'<br/>|\r|\u200B', '', content)

    # 步骤1：连续6个半角句号 → 全角省略号，连续4个及以上连字符 → 全角破折号（跳过表格分隔线）
    content = replace_outside_codeblocks(content, re.escape('......'), '……')
    content = replace_dashes_outside_codeblocks(content)

    # 步骤2：将半角引号替换为全角引号（相邻有 ASCII 字母/数字时不替换，保留为英文引号）
    content = process_paired_markers(content, '"', '“', '”', skip_when_ascii_adjacent=True)
    content = process_paired_markers(content, "'", '‘', '’', skip_when_ascii_adjacent=True)

    # 步骤3：在中文字符与英文/半角字符之间插入空格
    cjk = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]'
    hw  = r'[a-zA-Z0-9!@$%^&()\-=+{};:\'",.\/?]'
    content = re.sub(f'({cjk})({hw})', r'\1 \2', content)
    content = re.sub(f'({hw})({cjk})', r'\1 \2', content)

    # 步骤4：在数字和单位之间插入空格
    unit_whitelist = [
        "mal", "J", "mol", "m", "m/s", "J/mal", "g", "g/m³", "℃",
        "K", "°F", "°C",
        "s", "min", "h", "d",
        "cal", "eV", "Wh",
        "lb", "oz", "t", "u", "Da",
        "L", "gal",
        "N", "Pa", "bar", "atm", "torr", "psi", "mmHg",
        "A", "V", "W", "Ω", "Hz", "F", "H", "T", "S",
        "%", "dB", "pH", "B", "bit", "byte",
        "Å", "ft", "in", "mi", "nmi",
        "rad", "deg", "°",
        "M", "kat", "mol/L",
        "lm", "lx",
        "Bq", "Gy", "Sv", "C",
    ]
    sorted_units = sorted(unit_whitelist, key=len, reverse=True)
    escaped_units = [re.escape(u) for u in sorted_units]
    unit_alt = '|'.join(escaped_units)
    si_prefixes = r'(Y|Z|E|P|T|G|M|k|h|da|d|c|m|μ|n|p|f|a|z|y)?'
    num_unit_re = re.compile(rf'(\d+(?:\.\d+)?){si_prefixes}({unit_alt})(?!\w)')
    content = num_unit_re.sub(r'\1 \2\3', content)

    # 步骤5：处理斜体和加粗标记，在标记内部紧贴标记处插入零宽空格
    content = content.replace('**', "BOLD_PLACEHOLDER")
    content = process_paired_markers(content, '*', '*\u200B', '\u200B*', no_cross_newline=True)
    content = process_paired_markers(content, 'BOLD_PLACEHOLDER', '**\u200B', '\u200B**', no_cross_newline=True)

    # 步骤6：处理空行标准化
    content = re.sub(r' +\n', '\n', content)
    content = re.sub(r'\n +', '\n', content)
    while re.search(r'\n\n\n\n', content):
        content = re.sub(r'\n\n\n\n', '\n\n\n', content)
    content = re.sub(r'\n\n\n', 'THREE_NEWLINE_SOMETHING', content)

    content = replace_outside_codeblocks(content, r'\n\n', '\n')
    content = replace_outside_codeblocks(content, r'\|\n\|', 'TABLE_NEWLINE_SOMETHING')
    content = replace_outside_codeblocks(content, r'\n', '\n\n')
    content = content.replace('TABLE_NEWLINE_SOMETHING', '|\n|')

    content = re.sub(r'THREE_NEWLINE_SOMETHING', '\n<br/>\n<br/>\n<br/>\n<br/>\n\n', content)
    content = process_paired_markers(content, '\n\n```\n\n', '\n\n```\n', '\n```\n\n')

    # 将修改后的内容写回原文件
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

    print(f"[{filepath}] Modification complete.")


def main():
    if len(sys.argv) < 2:
        print("未指定文件，将遍历当前目录及所有子目录，标准化所有 .md 文件。")
        answer = input("是否继续？(Y/n): ").strip().lower()
        if answer and answer != 'y' and answer != 'yes':
            print("已取消。")
            sys.exit(0)

        md_files = []
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.endswith('.md') and '_Original' not in f:
                    md_files.append(os.path.join(root, f))

        if not md_files:
            print("未找到 .md 文件。")
            sys.exit(0)

        print(f"找到 {len(md_files)} 个 .md 文件，开始处理...")
        for filepath in md_files:
            process_file(filepath)
    else:
        for filepath in sys.argv[1:]:
            if '_Original' in os.path.basename(filepath):
                print(f"[{filepath}] 文件名包含 '_Original'，跳过。")
                continue
            process_file(filepath)

    print("All files processed.")
    time.sleep(0.5)
    sys.exit(0)

if __name__ == "__main__":
    main()