#!/usr/bin/env python3
"""
递归遍历当前目录及所有子目录，找到所有文件名匹配 `temp*.md` 的文件，
并以 UTF-8 无 BOM 编码写入一个换行符（即用单个 '\n' 替换原内容）。
"""

from pathlib import Path
import time

def reset_temp_md_files():
    base_dir = Path('.')
    # 递归匹配所有 temp*.md 文件（* 为通配符，包括 temp.md 本身）
    matched_files = list(base_dir.rglob('temp*.md'))

    if not matched_files:
        print("未找到任何匹配 temp*.md 的文件。")
        return

    print(f"找到 {len(matched_files)} 个文件，将用 UTF-8 换行符覆盖：")
    for fp in matched_files:
        print(f"  {fp}")

    # 可选确认步骤（需要时取消下面三行的注释）
    # confirm = input("确认覆盖以上文件？(y/N): ").strip().lower()
    # if confirm != 'y':
    #     print("操作已取消。")
    #     return

    for fp in matched_files:
        try:
            # 以 UTF-8 无 BOM 编码写入单个换行符
            fp.write_text('\n', encoding='utf-8')
            print(f"已处理: {fp}")
        except Exception as e:
            print(f"处理文件 {fp} 时出错: {e}")

if __name__ == "__main__":
    reset_temp_md_files()
    time.sleep(0.5)