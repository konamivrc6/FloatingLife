"""读取 .toolignore，提供统一的「该不该处理」判断。"""
import fnmatch
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IGNORE_FILE = os.path.join(_REPO_ROOT, '.toolignore')
_cache = None


def load_patterns():
    """返回 .toolignore 里的有效 glob 模式（去注释、去空行），读一次缓存。"""
    global _cache
    if _cache is not None:
        return _cache
    patterns = []
    if os.path.isfile(_IGNORE_FILE):
        with open(_IGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    _cache = patterns
    return patterns


def is_ignored(name):
    """name 为文件名（basename）；命中任一模式返回 True。"""
    name = os.path.normcase(os.path.basename(name))
    return any(fnmatch.fnmatch(name, p) for p in load_patterns())
