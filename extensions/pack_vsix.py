#!/usr/bin/env python3
"""把 extensions/<name>/ 打包成 .vsix。

用法：
    python pack_vsix.py <扩展文件夹名> [<扩展文件夹名> ...]
    python pack_vsix.py                          # 打包 extensions/ 下所有含 package.json 的子文件夹
"""
import json
import sys
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent

# 文件扩展名 -> OpenXML 内容类型（.vsix 是 zip，需要这份清单）
CONTENT_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".js": "application/javascript",
    ".cjs": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".xml": "application/xml",
    ".vsixmanifest": "text/xml",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
    ".toml": "application/octet-stream",
    ".txt": "text/plain",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}
DEFAULT_CONTENT_TYPE = "application/octet-stream"


def xml_escape(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_vsix(ext_dir):
    pkg = json.loads((ext_dir / "package.json").read_text(encoding="utf-8"))
    name = pkg["name"]
    publisher = pkg.get("publisher", "local")
    version = pkg.get("version", "0.0.1")
    display_name = pkg.get("displayName", name)
    description = pkg.get("description", "")
    engine = pkg.get("engines", {}).get("vscode", "^1.70.0")

    files = sorted(
        f.relative_to(ext_dir).as_posix() for f in ext_dir.rglob("*") if f.is_file()
    )

    assets = [
        '<Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json"/>'
    ]
    if "README.md" in files:
        assets.append(
            '<Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md"/>'
        )

    manifest = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PackageManifest Version="2.0.0" '
        'xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" '
        'xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">\n'
        "  <Metadata>\n"
        f'    <Identity Language="en-US" Id="{xml_escape(name)}" Version="{xml_escape(version)}" Publisher="{xml_escape(publisher)}"/>\n'
        f"    <DisplayName>{xml_escape(display_name)}</DisplayName>\n"
        f'    <Description xml:space="preserve">{xml_escape(description)}</Description>\n'
        "    <Properties>\n"
        f'      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{xml_escape(engine)}"/>\n'
        "    </Properties>\n"
        "  </Metadata>\n"
        "  <Installation>\n"
        '    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>\n'
        "  </Installation>\n"
        "  <Dependencies/>\n"
        "  <Assets>\n"
        + "\n".join(f"    {a}" for a in assets)
        + "\n  </Assets>\n"
        "</PackageManifest>\n"
    )

    exts = sorted({Path(f).suffix.lower() for f in files} | {".vsixmanifest"})
    type_entries = "\n".join(
        f'<Default Extension="{e.lstrip(".")}" ContentType="{CONTENT_TYPES.get(e, DEFAULT_CONTENT_TYPE)}"/>'
        for e in exts
    )
    content_types = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        f"{type_entries}\n"
        "</Types>\n"
    )

    out = BASE / f"{name}-{version}.vsix"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("extension.vsixmanifest", manifest)
        for rel in files:
            z.write(ext_dir / rel, f"extension/{rel}")

    return out, len(files)


def main(argv):
    names = argv[1:]
    if not names:
        names = [
            d.name
            for d in sorted(BASE.iterdir())
            if d.is_dir() and (d / "package.json").exists()
        ]
    if not names:
        print("未找到可打包的扩展（extensions/ 下没有含 package.json 的文件夹）。")
        return 1
    for n in names:
        ext_dir = BASE / n
        if not (ext_dir / "package.json").exists():
            print(f"跳过（无 package.json）：{n}")
            continue
        out, nfiles = build_vsix(ext_dir)
        print(f"已生成 {out.name}（{nfiles} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
