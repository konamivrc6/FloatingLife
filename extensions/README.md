# 扩展开发说明（维护者向）

这个目录放小说仓库自用的 VS Code 扩展，每个扩展一个子文件夹。`pack_vsix.py` 是共享的打包脚本。

## 打包 & 安装

```bash
python extensions/pack_vsix.py <扩展文件夹名> [<扩展文件夹名> ...]
# 不带参数 = 打包 extensions/ 下所有含 package.json 的子文件夹
```

生成 `.vsix` 后，VS Code 里 Ctrl + Shift + P，`Extensions: Install from VSIX...` 安装。

## floatinglife-markdown-highlight

给 Markdown 上色：`/* */` 注释（绿）、中文引号 `“ ”`/`「 」`、书名号 `《 》`（橙）。

### 核心架构：用装饰（decoration），不要用语法注入

**这是本项目最贵的一课。** 最初想用 TextMate 语法注入（grammar injection）让 `/* */` 被识别成注释，在 VS Code 1.135 上反复失灵：

1. `injectTo` 与 `language` 同时写 → `language` 让注入语法**取代** markdown 原生语法，整个文件只剩注释高亮。
2. 删掉 `language` 只留 `injectTo` → 冷启动后随机失效（「重启一次绿、再重启一次不绿」）。
3. 换成 `injectionSelector`（照搬大型扩展的写法）→ 照样飘。
4. 打包成正规 VSIX 安装 → 依旧不生效；`Inspect Editor Tokens and Scopes` 显示 `/* */` 仍是普通段落 scope。

结论：**语法注入在当前 VS Code 版本上不可靠**，跟 `injectTo`/`injectionSelector`/安装方式都无关。

最终方案：**JS 装饰**。扩展靠 `activationEvents: ["onLanguage:markdown"]` 激活后，用正则扫描文档，对匹配范围调 `createTextEditorDecorationType` 直接染色。这不经过语法层，确定性生效（参考 `floatinglife-markdown-highlight/main.js`）。

要点：
- `RULES` 数组描述高亮规则，每条含 `configKey`（配置键）、`defaultColor`、`regex`（带 `/g`）、`select(m)`（返回要染色的 `[起始偏移, 结束偏移]`）。
- 颜色走 `contributes.configuration`，用户可在设置里改。
- 「只染中间内容」用 `select: (m) => [m.index + 1, m.index + m[0].length - 1]`（前后标点各 1 字符）；「整段染色」用 `[m.index, m.index + m[0].length]`。

### 加一条新规则

在 `main.js` 的 `RULES` 里加一项，并在 `package.json` 的 `configuration.properties` 加对应颜色项：

```js
{
  configKey: 'xxxColor',
  defaultColor: '#RRGGBB',
  regex: /你的正则/g,
  select: (m) => [m.index, m.index + m[0].length],
}
```

「只有前引号、没有后引号就不高亮」这类需求，靠正则本身保证——写成 `前标[^后标]+后标`，天然要求成对出现。


### 踩过的坑（别重蹈）

- 语法注入的 `injectTo` / `injectionSelector` / `L:` 前缀 / scope 命名，在本机 VS Code 1.135 上都不稳——**别再用语法注入做高亮**。
- `editor.tokenColorCustomizations` 放在扩展的 `configurationDefaults` 里（尤其套 `[language]` 作用域）不可靠；要指定颜色就走 decoration 或用户设置。
- 正规 VSIX 安装（规范文件夹名 + uuid）比手动丢裸文件夹可靠，但**治不了注入失效**——根因是注入机制本身，不是安装方式。
- 正则里直接写中文标点没问题（文件是 UTF-8），不必转 `\u`；转义反而降低可读性。
- 扩展源码文件夹名要和 `package.json` 的 `name` 一致；VSIX 安装后会被 VS Code 命名为 `<publisher>.<name>-<version>`。
