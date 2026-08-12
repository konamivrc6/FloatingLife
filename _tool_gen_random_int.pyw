import tkinter as tk
import random
import math
from tkinter import font as tkfont

# 本福特定律首位数字1-9的概率权重
BENFORD_DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
BENFORD_WEIGHTS = [math.log10(1 + 1/d) for d in BENFORD_DIGITS]

class RandomDigitDisplay:
    def __init__(self, root):
        self.root = root
        self.root.title("随机数字生成器")
        self.root.geometry("800x200")
        
        # 存储最后42个数字
        self.digits = []
        self.max_digits = 42
        
        # 标记是否有生成过随机数
        self.has_generated = False
        
        # 设置窗口背景色
        self.root.configure(bg='black')
        
        # 创建自定义字体
        self.custom_font = tkfont.Font(family="Courier New", size=24, weight="bold")
        
        # 创建显示标签
        self.display_label = tk.Label(
            root,
            text="",
            font=self.custom_font,
            fg="#FFFFFF",  # 文字颜色
            bg='black',
            anchor='w',
            justify='left'
        )
        self.display_label.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 绑定键盘事件
        self.root.bind('<Key>', self.on_key_press)

        # 显示提示信息
        self.display_label.config(text="请按任意键开始生成随机数字...")
        
        # 使窗口获得焦点
        self.root.focus_set()
        
        # 添加说明标签
        self.instructions = tk.Label(
            root,
            text="按任意键生成随机数字(0-9) | 空格生成本福特数字(1-9) | Ctrl+C 复制 | ESC 清空/退出",
            font=("Arial", 10),
            fg='white',
            bg='black'
        )
        self.instructions.pack(side='bottom', pady=5)
        
        # 绑定ESC键
        self.root.bind('<Escape>', self.on_escape)
        
        # 绑定Ctrl+C复制
        self.root.bind('<Control-c>', self.on_copy)

    def on_key_press(self, event):
        # 排除ESC键、Ctrl键本身、以及Ctrl+C组合键
        if event.keysym == 'Escape':
            return
        if event.keysym in ('Control_L', 'Control_R'):
            return
        if event.state & 0x4 and event.keysym == 'c':
            return

        # 标记已生成过随机数
        self.has_generated = True

        # 空格键：生成本福特定律分布的数字（1-9）
        if event.keysym == 'space':
            random_digit = str(random.choices(BENFORD_DIGITS, weights=BENFORD_WEIGHTS)[0])
            # 闪烁绿色提示本福特数字
            self.display_label.config(fg="#FFD700")
            self.root.after(150, lambda: self.display_label.config(fg="#FFFFFF"))
        else:
            # 生成0-9的均匀随机数
            random_digit = str(random.randint(0, 9))

        # 将新数字添加到列表
        self.digits.append(random_digit)

        # 如果超过42个数字，移除最旧的数字
        if len(self.digits) > self.max_digits:
            self.digits.pop(0)

        # 更新显示文本
        display_text = ''.join(self.digits)
        self.display_label.config(text=display_text)

        # 更新说明文字
        self.instructions.config(text="按任意键生成随机数字(0-9) | 空格生成本福特数字(1-9) | Ctrl+C 复制 | ESC 清空")

    def on_copy(self, event):
        if not self.digits:
            return
        text = ''.join(self.digits)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()  # 确保剪贴板内容在窗口关闭后仍可使用
        
        # 短暂变色提示复制成功
        self.display_label.config(fg="#00FF88")
        self.root.after(200, lambda: self.display_label.config(fg="#FFFFFF"))

    def on_escape(self, event):
        if self.has_generated:
            # 清空所有数字
            self.digits.clear()
            self.display_label.config(text="")
            self.has_generated = False
            
            # 更新说明文字
            self.instructions.config(text="按任意键生成随机数字(0-9) | 空格生成本福特数字(1-9) | Ctrl+C 复制 | ESC 退出")
        else:
            # 退出程序
            self.root.quit()

def main():
    root = tk.Tk()
    app = RandomDigitDisplay(root)
    root.mainloop()

if __name__ == "__main__":
    main()
