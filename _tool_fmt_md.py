"""Markdown 排版标准化：备份 → 标准化 → 写回。

正文排版的唯一权威。全部排版步骤只作用于 fenced 代码块之外——每个行首围栏块（``` / ~~~，含围栏行本身与 info string）在管线开始前被整体遮成一个哨兵字符，管线跑完后逐字还原，因此代码块内容逐字节原样保留。

用法：python _tool_fmt_md.py [文件...]；不给参数则递归当前目录下所有未被 .toolignore 排除的 .md。

已知边界：围栏必须位于行首（可缩进）。`> ``` ` 这类嵌在引用块里的围栏匹配不到，其中的内容仍会被排版；未闭合的围栏同样不遮蔽。
"""

import os
import re
import shutil
import sys
import time

import _lib.toolignore as toolignore


# ── 跨步骤占位符：步骤0 写入，步骤8 统一还原 ──────────────────────────

SPAN_OPEN = '<span style="text-emphasis: dot; text-emphasis-position: under;">'
SPAN_CLOSE = '</span>'

DOT_START_TOKEN = 'DOT_START_PLACEHOLDER'
DOT_END_TOKEN = 'DOT_END_PLACEHOLDER'
COMMENT_START_TOKEN = 'COMMENTS_PLACEHOLDER_START'
COMMENT_END_TOKEN = 'COMMENTS_PLACEHOLDER_END'

# token → (还原文本, 是否吃掉紧邻的一个空格)
# eat_space=True 对应原先那 8 次顺序 replace：步骤3 会在占位符与中文之间插一个空格，原文本身也可能带一个，还原时吃掉左右各至多一个。这个吃空格是输出契约的一部分，不是顺手清理，不可改成不吃。
# eat_space=False 的两个注释占位符原样还原，不可改成 True。
# token 里不可出现连续两个下划线：步骤6 的 (?<!_)_(?!_) 保护不到 __，会被转义成 \_\_ 而还原失败。DOT 系的单下划线之所以能活过步骤6，是因为它先被换成下划线占位符、随后又换回来——改名只要不含 __ 就安全。
PLACEHOLDERS = {
    DOT_START_TOKEN: (SPAN_OPEN, True),
    DOT_END_TOKEN: (SPAN_CLOSE, True),
    COMMENT_START_TOKEN: ('/*', False),
    COMMENT_END_TOKEN: ('*/', False),
}


# ── 步骤内临时占位符：只在一个步骤内生存，用完立即还原，不参与步骤8 ──────

BOLD_TOKEN = 'BOLD_PLACEHOLDER'
UNDERSCORE_TOKEN = 'SINGLE-UNDERSCORE-PLACEHOLDER'
LARGE_BLANK_TOKEN = 'LARGE_BLANK_SOMETHING'
TABLE_NL_TOKEN = 'TABLE_NEWLINE_SOMETHING'


# ── 围栏遮蔽 ──────────────────────────────────────────────────────

# BMP 私有区单字符。非 ASCII、非 CJK、非标点，所以步骤1-6 的正则与 process_paired_markers 的字符扫描都不可能碰到它。
# 用固定哨兵 + 按位置还原，不要用 chr(0xE000 + i)：索引数字是 ASCII 且落在步骤3 的 HW 类里，一旦与中文相邻就会被插空格；索引一大还会走出私有区撞进 CJK 区间。
# 哨兵之所以安全：原先落在围栏边界上的字符只可能是反引号或换行，两者都不在 HW 类、也不在 CJK 类里，所以步骤2/3/4 本来就不可能在边界开火；哨兵同样两者都不是。
CODE_SENTINEL = '\uE000'
CODE_SENTINEL_RE = re.compile(re.escape(CODE_SENTINEL))

# 围栏：行首（可缩进）连续 3 个以上 ` 或 ~，可带 info string；闭合围栏须同缩进、以同一串围栏字符起始，反向引用保证 ``` 与 ~~~ 不会互相闭合。
# 匹配范围不含开头行之前的换行、也不含闭合行之后的换行——否则会吃掉围栏与相邻空行之间的换行，使步骤7 的「拆空行再翻倍」在围栏两侧与今天不一致。
FENCE_RE = re.compile(r'^([ \t]*)(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1\2[^\n]*$', re.M)


def mask_code_blocks(text):
    """把每个行首 fenced 代码块（含围栏行本身）整体换成哨兵，返回 (掩码文本, 原始块列表)。"""
    blocks = []

    def take(match):
        blocks.append(match.group(0))
        return CODE_SENTINEL

    return FENCE_RE.sub(take, text), blocks


def unmask_code_blocks(masked, blocks):
    """按出现顺序把哨兵还原为原始块；数量不符直接报错，绝不静默吃掉内容。"""
    remaining = iter(blocks)

    def put(_match):
        try:
            return next(remaining)
        except StopIteration:
            raise ValueError('代码块哨兵数量不匹配：某个步骤改动了哨兵本身')

    text = CODE_SENTINEL_RE.sub(put, masked)
    if CODE_SENTINEL in text:
        raise ValueError('代码块哨兵数量不匹配：还原后仍有残留哨兵')
    return text


def assert_placeholders_absent(text, filepath):
    """源文件里若已出现占位符或哨兵文本，直接报错退出：宁可停下，也不要静默改坏内容。

    这一并覆盖哨兵：源文件里若已有 U+E000 而没有围栏，会走到 unmask 的 StopIteration；若有围栏，则会静默还原成错误的块。前置检查把两种情况变成一条清晰报错。
    """
    candidates = list(PLACEHOLDERS) + [BOLD_TOKEN, UNDERSCORE_TOKEN, LARGE_BLANK_TOKEN, TABLE_NL_TOKEN, CODE_SENTINEL]
    offenders = [token for token in candidates if token in text]
    if offenders:
        raise SystemExit(f"[{filepath}] 源文件已包含占位符文本 {offenders}，请先改名后重跑；本次未做任何修改。")


# ── 数字与单位 ────────────────────────────────────────────────────

UNIT_WHITELIST = "mal J mol m m/s J/mal g g/m³ ℃ K °F °C s min h d cal eV Wh lb oz t u Da L gal N Pa bar atm torr psi mmHg A V W Ω Hz F H T S % dB pH B bit byte Å ft in mi nmi rad deg ° M kat mol/L lm lx Bq Gy Sv C".split()
SI_PREFIX = r'(Y|Z|E|P|T|G|M|k|h|da|d|c|m|μ|n|p|f|a|z|y)?'


def _build_number_unit_re():
    """单位按长度降序排成交替串，避免短单位先匹配、把长单位截断。"""
    alternatives = '|'.join(re.escape(unit) for unit in sorted(UNIT_WHITELIST, key=len, reverse=True))
    return re.compile(rf'(\d+(?:\.\d+)?){SI_PREFIX}({alternatives})(?!\w)')


NUMBER_UNIT_RE = _build_number_unit_re()


# ── 中英之间的间距字符类 ──────────────────────────────────────────

CJK = '[\u4e00-\u9fff\u3400-\u4dbf\uF900-\uFAFF]'
HW = r'[a-zA-Z0-9!@$%^&()\-=+{};:\'",.\/?]'


# ── 成对标记扫描 ──────────────────────────────────────────────────


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
                if (prev_char and prev_char.isascii() and prev_char.isalnum()) or \
                   (next_char and next_char.isascii() and next_char.isalnum()):
                    result.append(marker)
                    i += marker_len
                    continue
            if no_cross_newline and is_open:
                next_pos = text.find(marker, i + marker_len)
                if next_pos == -1:
                    result.append(text[i:])
                    break
                if '\n' in text[i + marker_len:next_pos]:
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


# ── 各步骤 ────────────────────────────────────────────────────────


def step_hygiene(text):
    """原步骤0 前半：删除 <br/> 与零宽空格。跑在掩码之后，所以围栏里的它们会被保留。"""
    return re.sub('<br/>|\u200B', '', text)


def mask_deferred_placeholders(text):
    """原步骤0 后半：把 DOT span 的两个标签藏成占位符，步骤8 统一还原。"""
    text = text.replace(SPAN_OPEN, DOT_START_TOKEN)
    text = text.replace(SPAN_CLOSE, DOT_END_TOKEN)
    return text


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


def step_punctuation(text):
    """原步骤1：连续6个半角句号 → 全角省略号，连续4个及以上连字符 → 全角破折号（跳过表格分隔线）。"""
    text = re.sub(re.escape('......'), '……', text)
    return re.sub(r'-{4,}', _replace_dashes_callback, text)


def step_quotes(text):
    """原步骤2：将半角引号替换为全角引号（相邻有 ASCII 字母/数字时不替换，保留为英文引号）。"""
    text = process_paired_markers(text, '"', '“', '”', skip_when_ascii_adjacent=True)
    return process_paired_markers(text, "'", '‘', '’', skip_when_ascii_adjacent=True)


def step_cjk_ascii_space(text):
    """原步骤3：在中文字符与英文/半角字符之间插入空格。"""
    text = re.sub(f'({CJK})({HW})', r'\1 \2', text)
    return re.sub(f'({HW})({CJK})', r'\1 \2', text)


def step_number_unit_space(text):
    """原步骤4：在数字和单位之间插入空格。"""
    return NUMBER_UNIT_RE.sub(r'\1 \2\3', text)


def step_emphasis(text):
    """原步骤5：处理斜体和加粗标记，在标记内部紧贴标记处插入零宽空格。"""
    text = text.replace('/*', COMMENT_START_TOKEN)
    text = text.replace('*/', COMMENT_END_TOKEN)
    text = text.replace('**', BOLD_TOKEN)
    text = process_paired_markers(text, '*', '*\u200B', '\u200B*', no_cross_newline=True)
    return process_paired_markers(text, BOLD_TOKEN, '**\u200B', '\u200B**', no_cross_newline=True)


def step_underscore(text):
    """原步骤6：对下划线转义。"""
    text = text.replace('\\_', '_')
    text = re.sub(r'(?<!_)_(?!_)', UNDERSCORE_TOKEN, text)
    text = text.replace('_', '\\_')
    return text.replace(UNDERSCORE_TOKEN, '_')


def step_blank_lines(text):
    """原步骤7：处理空行标准化——删行尾空格、压缩连续空行、把三连空行展开成 <br/> 段、保护表格行、合并引用行。

    内部顺序是承重的，不可重排：LARGE_BLANK 的展开必须留在原位，因为它引入真换行与 <br/> 行，紧随的引用行合并依赖这个位置。
    """
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    while re.search(r'\n\n\n\n', text):
        text = re.sub(r'\n\n\n\n', '\n\n\n', text)
    text = text.replace('\n\n\n', LARGE_BLANK_TOKEN)

    text = re.sub(r'\n\n', '\n', text)
    text = re.sub(r'\|\n\|', TABLE_NL_TOKEN, text)
    text = re.sub(r'\n', '\n\n', text)
    text = text.replace(TABLE_NL_TOKEN, '|\n|')

    text = text.replace(LARGE_BLANK_TOKEN, '\n\n<br/>\n<br/>\n<br/>\n\n')
    text = re.sub(r'(>[^\n]*)\n\n(>)', r'\1\n\2', text)
    return text.replace('>\n\n>', '>\n>')


def restore_placeholders(text):
    """原步骤8：统一还原跨步骤占位符；空格敏感的条目吃掉紧邻的一个空格（与原 8 次 replace 逐字节等价）。"""
    for token, (original, eat_space) in PLACEHOLDERS.items():
        pattern = (' ?' + re.escape(token) + ' ?') if eat_space else re.escape(token)
        text = re.sub(pattern, lambda _match: original, text)
    return text


# ── 管线 ──────────────────────────────────────────────────────────


def format_markdown(text):
    """排版规范化主流程：fenced 代码块整体绕过全部步骤，最后逐字还原。"""
    # 行尾统一 LF。\r 被当作文件卫生而非排版，所以放在掩码之前、仍然全局生效；否则 \r 会被存进代码块里原样还原，CRLF 输入会变成「围栏外 LF、围栏内 CRLF」的混合行尾。
    text = text.replace('\r', '')
    text, blocks = mask_code_blocks(text)
    text = step_hygiene(text)
    text = mask_deferred_placeholders(text)
    text = step_punctuation(text)
    text = step_quotes(text)
    text = step_cjk_ascii_space(text)
    text = step_number_unit_space(text)
    text = step_emphasis(text)
    text = step_underscore(text)
    text = step_blank_lines(text)
    text = restore_placeholders(text)
    return unmask_code_blocks(text, blocks)


def process_file(filepath):
    """处理单个 Markdown 文件：备份 → 标准化 → 写回。"""
    if not os.path.isfile(filepath):
        print(f"Error: file '{filepath}' not found. Skipping.")
        return

    with open(filepath, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    # 放在备份之前：命中时不留下 _Original 残骸
    assert_placeholders_absent(content, filepath)

    base, ext = os.path.splitext(filepath)
    backup_path = base + "_Original" + ext

    shutil.copy2(filepath, backup_path)
    print(f"[{filepath}] Backup saved as: {backup_path}")

    content = format_markdown(content)

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

    print(f"[{filepath}] Modification complete.")


def collect_targets(args):
    """收集待处理文件：给了参数就用参数（逐个查忽略规则并打印），否则递归当前目录下的 .md。"""
    if args:
        targets = []
        for filepath in args:
            if toolignore.is_ignored(os.path.basename(filepath)):
                print(f"[{filepath}] 命中忽略规则，跳过。")
                continue
            targets.append(filepath)
        return targets

    md_files = []
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.md') and not toolignore.is_ignored(f):
                md_files.append(os.path.join(root, f))
    return md_files


def main():
    args = sys.argv[1:]
    if not args:
        print("未指定文件，将遍历当前目录及所有子目录，标准化所有 .md 文件。")
        answer = input("是否继续？(Y/n): ").strip().lower()
        if answer and answer not in ('y', 'yes'):
            print("已取消。")
            sys.exit(0)

    targets = collect_targets(args)

    # 「未找到」只在递归模式下打印，与现状一致
    if not args and not targets:
        print("未找到 .md 文件。")
        sys.exit(0)

    if not args:
        print(f"找到 {len(targets)} 个 .md 文件，开始处理...")
    for filepath in targets:
        process_file(filepath)

    print("All files processed.")
    time.sleep(0.5)
    sys.exit(0)


if __name__ == "__main__":
    main()
