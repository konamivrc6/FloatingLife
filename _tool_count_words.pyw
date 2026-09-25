import tkinter as tk
import re
import sys

# ── 颜色（黑白极简）─────────────────────────────────────────────────────────
BG        = "#000000"   # 纯黑背景
SURFACE   = "#0f0f0f"   # 卡片背景
BORDER    = "#2a2a2a"   # 边框
TEXT_MAIN = "#b1b1b1"   # 主文字
TEXT_DIM  = "#b1b1b1"   # 次要文字（当前与 TEXT_MAIN 同色）
ACCENT    = "#ffffff"   # 强调（白）
INPUT_BG  = "#0a0a0a"   # 输入框背景
CURSOR    = "#ffffff"   # 光标
SEL_BG    = "#333333"   # 选中背景


def strip_markup(text: str) -> str:
    """剥掉不该计入字数的标记。

    只处理四类：作者注、HTML 标签、标题行的 # 与章节序号、零宽空格。
    `*斜体*` 的星号、表格 `|`、列表 `-` 都当正文内容保留。
    """
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)          # 作者注可跨行；build.py 的 strip_comments() 也会删
    text = re.sub(r'<[^>]+>', '', text)                        # <br/> <br> <u> </u> 等
    text = re.sub(r'^#{1,6}\s+\d*\s*', '', text, flags=re.M)   # 标题行的 # 与章节序号，标题文字保留
    return text.replace(chr(0x200b), '')                     # _tool_fmt_md.py 插在 * 内侧的零宽空格


def count_stats(text: str) -> dict:
    text          = strip_markup(text)
    no_space      = re.sub(r'\s', '', text)
    char_count    = len(no_space)

    hanzi         = re.findall(
        r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df]', text)
    hanzi_count   = len(hanzi)

    # 逐个区间列举，跳过夹在里面的非标点码位：全角空格 U+3000、全角字母数字
    # U+FF10-19/21-3A/41-5A、々〆 之类符号、〡-〩 中文数字。
    # 早先整段收 U+FF00-FFEF，会把全角字母数字一并当成标点。
    cn_punct      = re.findall(
        r'[\u3001-\u3003\u3008-\u3011\u3014-\u301f'
        r'\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65'
        r'\u2013\u2014\u2018\u2019\u201c\u201d\u2026\u22ef\u00b7\u30fb]',
        text)
    cn_punct_count = len(cn_punct)

    hanzi_with_punct = hanzi_count + cn_punct_count

    en_words      = re.findall(
        r"[A-Za-z0-9]+(?:['\u2019\-][A-Za-z0-9]+)*", text)
    en_word_count = len(en_words)

    standard = hanzi_count + cn_punct_count + en_word_count

    return {
        "char":        char_count,
        "hanzi":       hanzi_count,
        "hanzi_punct": hanzi_with_punct,
        "en_words":    en_word_count,
        "standard":    standard,
    }


def load_file(path: str):
    """读文件内容（utf-8-sig，兼容 BOM）；失败打印错误并返回 None。"""
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return f.read()
    except OSError as e:
        print(f"无法读取 {path}: {e}", file=sys.stderr)
        return None


class WordCounter(tk.Tk):
    WIN_W, WIN_H = 600, 350

    def __init__(self, initial_text=None):
        super().__init__()
        self.title("Word Counter")
        self.configure(bg=BG)

        # 锁死尺寸
        self.resizable(False, False)
        self.update_idletasks()
        self.geometry(f"{self.WIN_W}x{self.WIN_H}")

        self._build_ui()
        self._update_stats()

        # 焦点永远在输入框
        self.text_box.focus_set()
        self.bind("<FocusIn>", self._refocus)
        self.text_box.bind("<FocusOut>", self._refocus)

        self.bind("<Escape>", self._on_escape)

        if initial_text:
            self._load_text(initial_text)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 标题栏
        header = tk.Frame(self, bg=BG, pady=12)
        header.pack(fill="x", padx=20)
        tk.Label(header, text="Word Counter",
                 font=("Helvetica", 15, "bold"),
                 fg=TEXT_MAIN, bg=BG).pack(side="left")
        tk.Label(header, text="Esc 清空 / 退出",
                 font=("Helvetica", 9), fg=TEXT_DIM, bg=BG).pack(side="right")

        # 分隔线
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── 输入框（较小，固定高度）──────────────────────────────────────────
        input_wrap = tk.Frame(self, bg=BORDER, highlightthickness=0)
        input_wrap.pack(fill="x", padx=20, pady=(14, 10))

        inner = tk.Frame(input_wrap, bg=INPUT_BG)
        inner.pack(fill="x", padx=1, pady=1)

        self.text_box = tk.Text(
            inner,
            font=("Helvetica", 12),
            bg=INPUT_BG, fg=TEXT_MAIN,
            insertbackground=CURSOR,
            selectbackground=SEL_BG, selectforeground=TEXT_MAIN,
            relief="flat", bd=0,
            padx=12, pady=10,
            wrap="word",
            undo=True,
            height=6,          # 固定行高（较小）
        )
        self.text_box.pack(fill="x", side="left", expand=True)

        sb = tk.Scrollbar(inner, command=self.text_box.yview,
                          bg=SURFACE, troughcolor=INPUT_BG,
                          activebackground=BORDER,
                          relief="flat", width=6, bd=0)
        sb.pack(side="right", fill="y")
        self.text_box.configure(yscrollcommand=sb.set)

        self.text_box.bind("<<Modified>>", self._on_modified)

        # 占位文字
        self._ph_active = True
        self._PLACEHOLDER = "在此输入文本……"
        self.text_box.insert("1.0", self._PLACEHOLDER)
        self.text_box.config(fg=TEXT_DIM)
        self.text_box.bind("<Key>", self._clear_placeholder)

        # ── 统计面板 ─────────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=0)

        stats_frame = tk.Frame(self, bg=BG)
        stats_frame.pack(fill="both", expand=True, padx=20, pady=16)

        STATS = [
            ("char",        "字符数",           TEXT_MAIN),
            ("hanzi",       "汉字（无标点）",  TEXT_MAIN),
            ("hanzi_punct", "汉字（含标点）",    TEXT_MAIN),
            ("en_words",    "西文词数",          TEXT_MAIN),
            ("standard",    "含标点字数",        ACCENT),
        ]

        self._stat_vars = {}
        for col in range(5):
            stats_frame.columnconfigure(col, weight=1)

        for i, (key, label, color) in enumerate(STATS):
            card = tk.Frame(stats_frame, bg=SURFACE,
                            highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            stats_frame.rowconfigure(0, weight=1)

            tk.Label(card, text=label, font=("Helvetica", 8),
                     fg=TEXT_DIM, bg=SURFACE, pady=8, wraplength=90).pack()

            var = tk.StringVar(value="0")
            self._stat_vars[key] = var
            tk.Label(card, textvariable=var,
                     font=("Helvetica", 26, "bold"),
                     fg=color, bg=SURFACE, pady=4).pack()

    # ── 逻辑 ─────────────────────────────────────────────────────────────────

    def _refocus(self, event=None):
        """任何时候失焦都拉回输入框"""
        self.after(10, self.text_box.focus_set)

    def _get_text(self) -> str:
        return "" if self._ph_active else self.text_box.get("1.0", "end-1c")

    def _on_modified(self, event=None):
        self.text_box.edit_modified(False)
        self._update_stats()

    def _update_stats(self):
        stats = count_stats(self._get_text())
        for key, var in self._stat_vars.items():
            var.set(str(stats[key]))

    def _load_text(self, text: str):
        """把文本填进输入框并清掉占位状态（供命令行/拖放传入文件时用）。"""
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        self.text_box.config(fg=TEXT_MAIN)
        self._ph_active = False
        self._update_stats()

    def _on_escape(self, event=None):
        if self._get_text().strip():
            self.text_box.delete("1.0", "end")
            self._ph_active = True
            self.text_box.insert("1.0", self._PLACEHOLDER)
            self.text_box.config(fg=TEXT_DIM)
            self._update_stats()
        else:
            self.destroy()

    def _clear_placeholder(self, event=None):
        if self._ph_active:
            # 仅在用户输入可见字符时清除占位文字，忽略方向键等控制键
            if event and not event.char:
                return
            self.text_box.delete("1.0", "end")
            self.text_box.config(fg=TEXT_MAIN)
            self._ph_active = False


def main():
    if sys.stdout is None:
        # pythonw 双击 / 拖放文件启动：无控制台 → GUI；给了文件就填进输入框
        path = sys.argv[1] if len(sys.argv) > 1 else None
        app = WordCounter(initial_text=load_file(path) if path else None)
        app.mainloop()
        return

    # 控制台启动：CLI 模式，必须给文件
    if len(sys.argv) < 2:
        print('用法：python _tool_count_words.pyw <文件.md>')
        sys.exit(1)

    text = load_file(sys.argv[1])
    if text is None:
        sys.exit(1)

    stats = count_stats(text)
    for label, key in [
        ("字符数",        "char"),
        ("汉字（无标点）", "hanzi"),
        ("汉字（含标点）", "hanzi_punct"),
        ("西文词数",      "en_words"),
        ("含标点字数",    "standard"),
    ]:
        print(f"{label}: {stats[key]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
