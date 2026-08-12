import tkinter as tk
import re

# ── 颜色（黑白极简）─────────────────────────────────────────────────────────
BG        = "#000000"   # 纯黑背景
SURFACE   = "#0f0f0f"   # 卡片背景
BORDER    = "#2a2a2a"   # 边框
TEXT_MAIN = "#b1b1b1"   # 主文字
TEXT_DIM  = "#b1b1b1"   # 暗灰次要文字
ACCENT    = "#ffffff"   # 强调（白）
ACCENT2   = "#d6d6d6"   # 弱强调（浅灰，用于标准字数）
INPUT_BG  = "#0a0a0a"   # 输入框背景
CURSOR    = "#ffffff"   # 光标
SEL_BG    = "#333333"   # 选中背景


def count_stats(text: str) -> dict:
    no_space      = re.sub(r'\s', '', text)
    char_count    = len(no_space)

    hanzi         = re.findall(
        r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df]', text)
    hanzi_count   = len(hanzi)

    cn_punct      = re.findall(
        r'[\u3000-\u303f\uff00-\uffef'
        r'\u2018\u2019\u201c\u201d\u2014\u2026\u00b7\u300a\u300b\u3008\u3009]',
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


class WordCounter(tk.Tk):
    WIN_W, WIN_H = 600, 350

    def __init__(self):
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
            ("standard",    "标准字数",          ACCENT),
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


if __name__ == "__main__":
    app = WordCounter()
    app.mainloop()
