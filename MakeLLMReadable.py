import sys
import re
import os
import time
import subprocess
import platform

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 删除所有 /* */ 包裹的注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    # 删除所有 <br/>
    content = content.replace('<br/>', '')

    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)

    header = f'[file name: {filename}]\n[file begins]\n'
    footer = '\n[file ends]'

    result = header + content + footer

    out_dir = os.path.dirname(filepath)
    out_name = f'{name}_LLM{ext}'
    out_path = os.path.join(out_dir, out_name) if out_dir else out_name

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f'已输出到: {out_path}')

    copy_to_clipboard(result)


def copy_to_clipboard(text):
    system = platform.system()
    try:
        if system == 'Windows':
            subprocess.run(['clip'], input=text.encode('utf-16-le'), check=True)
            print('已复制到剪贴板 (clip)')
        elif system == 'Darwin':
            subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
            print('已复制到剪贴板 (pbcopy)')
        else:
            for cmd in ['xclip -selection clipboard', 'xsel --clipboard --input']:
                try:
                    subprocess.run(cmd.split(), input=text.encode('utf-8'), check=True)
                    print(f'已复制到剪贴板 ({cmd.split()[0]})')
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            print('警告: 未找到 xclip 或 xsel，无法复制到剪贴板')
    except Exception as e:
        print(f'警告: 剪贴板复制失败 ({e})')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python MakeLLMReadable.py <文件路径>')
        time.sleep(1)
        sys.exit(1)

    process_file(sys.argv[1])
