#!/usr/bin/env python3
"""
递归扫描当前目录及子目录中的 .txt, .py, .md 文件，
移除 UTF-8 BOM（字节 EF BB BF）。
运行时列出文件并需要用户确认后才执行。
"""

import sys
from pathlib import Path

# 需要处理的文件扩展名（不区分大小写）
TARGET_EXTENSIONS = {'.txt', '.py', '.md'}
UTF8_BOM = b'\xef\xbb\xbf'


def has_utf8_bom(file_path: Path) -> bool:
    """检查文件是否以 UTF-8 BOM 开头。"""
    try:
        with file_path.open('rb') as f:
            return f.read(3) == UTF8_BOM
    except (OSError, IOError):
        return False


def remove_utf8_bom(file_path: Path) -> bool:
    """
    移除文件的 UTF-8 BOM，直接覆盖原文件。
    返回 True 表示成功，False 表示失败。
    """
    try:
        with file_path.open('rb') as f:
            content = f.read()
        if content.startswith(UTF8_BOM):
            # 去掉 BOM 后写回
            with file_path.open('wb') as f:
                f.write(content[3:])
            return True
        # 没有 BOM（理论上不会发生，但防御一下）
        return False
    except (OSError, IOError) as e:
        print(f"错误：无法处理 {file_path} - {e}", file=sys.stderr)
        return False


def find_bom_files(root_dir: str = '.') -> list[Path]:
    """
    递归查找 root_dir 下所有匹配扩展名且带有 BOM 的文件。
    返回 Path 对象列表。
    """
    root = Path(root_dir).resolve()
    bom_files = []
    for entry in root.rglob('*'):
        if entry.is_file() and entry.suffix.lower() in TARGET_EXTENSIONS:
            if has_utf8_bom(entry):
                bom_files.append(entry)
    return bom_files


def main():
    print("正在搜索含有 UTF-8 BOM 的文件...")
    files = find_bom_files()

    if not files:
        print("未找到任何含有 UTF-8 BOM 的 .txt, .py, .md 文件。")
        return

    # 列出将要处理的文件
    print(f"\n找到 {len(files)} 个含有 BOM 的文件：")
    for i, f in enumerate(files, 1):
        print(f"  {i:>3}. {f}")

    # 用户确认
    print("\n⚠ 将永久删除以上文件开头的 UTF-8 BOM 字节（操作不可逆）。")
    # 添加 flush 以保证提示信息在交互环境及时显示
    try:
        confirm = input("确认执行？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消。")
        return

    if confirm != 'y':
        print("操作已取消。")
        return

    # 执行移除
    success = 0
    for f in files:
        if remove_utf8_bom(f):
            print(f"✓ 已移除 BOM: {f}")
            success += 1
        else:
            print(f"✗ 移除失败: {f}")

    print(f"\n完成：成功处理 {success} / {len(files)} 个文件。")


if __name__ == '__main__':
    main()