import os

def main():
    root = os.getcwd()
    to_delete = []

    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if '_Original' in f:
                full_path = os.path.join(dirpath, f)
                to_delete.append(full_path)

    if not to_delete:
        print("未找到任何包含 _Original 标记的文件。")
        input("按 Enter 退出...")
        return

    print("即将删除以下文件：\n")
    for path in to_delete:
        print(f"  {path}")

    print(f"\n共 {len(to_delete)} 个文件。")
    confirm = input("\n确认删除？输入 y 确认，其他任意键取消：")

    if confirm.strip().lower() == 'y':
        for path in to_delete:
            os.remove(path)
            print(f"已删除: {path}")
        print("\n删除完成。")
    else:
        print("已取消删除。")
        input("按 Enter 退出...")

if __name__ == "__main__":
    main()
