# 扩展开发说明（维护者向）

这个目录放小说仓库自用的 VS Code 扩展，每个扩展一个子文件夹。`pack_vsix.py` 是共享的打包脚本。

目前有两个：

- `floatinglife-markdown-highlight`，负责静态正则染色和最近 7 秒输入的临时染色。

- `markdown-fmt-runner`，在 Markdown 里敲 `///fmt` 再回车，调用 `_tool_fmt_md.py` 排版当前文件。它的名称与设置项刻意不带项目名，方便挪到别的仓库用。

## 打包 & 安装

```bash
python extensions/pack_vsix.py <扩展文件夹名> [<扩展文件夹名> ...]
# 不带参数 = 打包 extensions/ 下所有含 package.json 的子文件夹
```

生成 `.vsix` 后，VS Code 里 Ctrl + Shift + P，`Extensions: Install from VSIX...` 安装。

## floatinglife-markdown-highlight

给 Markdown 上色：`/* */` 注释（绿）、中文引号 `“ ”`/`「 」`、书名号 `《 》`（橙），以及 `###` 标题标签——时间标签 `timeX` 黄、`丢弃` 红、`完成` 绿、其他标签与 `_` 灰。

### 核心架构：用装饰（decoration），不要用语法注入

**​这是本项目最贵的一课。​** 最初想用 TextMate 语法注入（grammar injection）让 `/* */` 被识别成注释，在 VS Code 1.135 上反复失灵：

1. `injectTo` 与 `language` 同时写 → `language` 让注入语法**​取代​** markdown 原生语法，整个文件只剩注释高亮。

2. 删掉 `language` 只留 `injectTo` → 冷启动后随机失效（「重启一次绿、再重启一次不绿」）。

3. 换成 `injectionSelector`（照搬大型扩展的写法）→ 照样飘。

4. 打包成正规 VSIX 安装 → 依旧不生效；`Inspect Editor Tokens and Scopes` 显示 `/* */` 仍是普通段落 scope。

结论：**​语法注入在当前 VS Code 版本上不可靠​**，跟 `injectTo`/`injectionSelector`/ 安装方式都无关。

最终方案：**​JS 装饰​**。扩展靠 `activationEvents: ["onLanguage:markdown"]` 激活后，用正则扫描文档，对匹配范围调 `createTextEditorDecorationType` 直接染色。这不经过语法层，确定性生效（参考 `floatinglife-markdown-highlight/main.js`）。

要点：

- `RULES` 数组描述高亮规则，每条含 `configKey`（配置键）、`defaultColor`、`regex`（带 `/g`）、`select(m)`（返回**​若干 `[起始偏移 , 结束偏移]` 组成的数组​**，可为空）。

- 颜色走 `contributes.configuration`，用户可在设置里改。

- 整段染色返回单元素数组，如 `select: (m) => [[m.index, m.index + m[0].length]]`；多段（如一条正则要把不同子串拆到不同颜色桶）返回多元素数组。

- 同一 `select` 内不允许区间重叠——不同颜色分给不同 rule，让 rule 的正则各自只匹配自己那份子串即可。

### 加一条新规则

在 `main.js` 的 `RULES` 里加一项，并在 `package.json` 的 `configuration.properties` 加对应颜色项：

```js
{
  configKey: 'xxxColor',
  defaultColor: '#RRGGBB',
  regex: /你的正则/g,
  select: (m) => [[m.index, m.index + m[0].length]],
}
```

`###` 标题标签的高亮（`main.js` 里 `timeTagColor` 等 4 条）做法：用

`/^### .*​?(_[^\n]​*)$/gm` 只匹配「从第一个 `_` 起的标签区」为捕获组 1（标题文字不含 `_`，

故首个 `_` 之前全是标题），再用 `tagPairs(m, kind)` 把该区段拆成 token，按时间 / 丢弃 / 完成 / 其他

分类返回各 `[s,e]` 区间。`_` 与「杂项标签」归 `other`，时间标签复用

`/^time-?\d+(?:\.\d+)?$/`（与 `_tool_fix_chapters.py` 的 `timeX` 规则一致，含小数 / 负数）。

「只有前引号、没有后引号就不高亮」这类需求，靠正则本身保证——写成 `前标[^ 后标]+ 后标`，天然要求成对出现。

### 踩过的坑（别重蹈）

- 语法注入的 `injectTo` / `injectionSelector` / `L:` 前缀 / scope 命名，在本机 VS Code 1.135 上都不稳——**​别再用语法注入做高亮​**。

- `editor.tokenColorCustomizations` 放在扩展的 `configurationDefaults` 里（尤其套 `[language]` 作用域）不可靠；要指定颜色就走 decoration 或用户设置。

- 正规 VSIX 安装（规范文件夹名 + uuid）比手动丢裸文件夹可靠，但**​治不了注入失效​**——根因是注入机制本身，不是安装方式。

- 正则里直接写中文标点没问题（文件是 UTF-8），不必转 `\u`；转义反而降低可读性。

- 扩展源码文件夹名要和 `package.json` 的 `name` 一致；VSIX 安装后会被 VS Code 命名为 `<publisher>.<name>-<version>`。

### 最近输入高亮（瞬态）

最近 7 秒内输入的字符染上紫色，到期恢复原色。颜色和时长是 `main.js` 顶部的常量，没有配置项。

它和 `RULES` 不是一类东西——**​时序状态​**，不是正则规则：

- 按文档维护 `{start, end, expireAt}` 表，偏移是 UTF-16 code unit，与 `rangeOffset` / `positionAt` 同制。

- 监听 `onDidChangeTextDocument`，用 `contentChanges` 平移已有区间。VS Code 按 `rangeOffset` **​降序​**给出改动，且坐标都是**​改动前​**的；旧区间按降序变换，新插入的区间按升序累加长度差换算到改动后的坐标。

- 静态区间也存在缓存 `staticByDoc` 里跟着编辑平移（`transformStaticRange`）。纯插入落在区间内部时，静态区间要**​扩张​**包住新字，瞬态区间则要**​拆开​**把新字留给新条目；停手后的全文重扫会修正平移产生的漂移。

- 渲染必须**​同步​**：任何去抖计时器在连续打字时都永远不到点。

- 一个自续的 `setTimeout` 总是指向最早的 `expireAt`，到点删条目、把静态区间补回来、重绘。

- 应用静态规则前先 `subtractTyped()` 把最近输入的区间挖掉。**​同一段文字只落进一种装饰​**，紫色能不能显示就不再取决于 VS Code 的层叠顺序。

### 为什么不再拆成两个扩展

最初把瞬态高亮做成了独立扩展 `floatinglife-typing-highlight`，好处是开关走扩展面板、不用配置项。但两个扩展各建装饰类型、对同一段文字设 `color` 时，VS Code 的层叠结果从扩展侧控制不了：

- 「后来创建的类型赢」——每轮打字开头销毁重建装饰类型，实测无效。

- 「后 `setDecorations` 的赢」——晚于静态扩展 150 ms 去抖补刷一次，实测也无效。

所以合并回一个扩展，用**​区间相减​**从根上避免重叠。代价是：现在禁用扩展会同时关掉静态高亮和输入高亮。

**​不要把它镜像进 `_tool_export_colored.py`​**：瞬态高亮依赖时间，静态导出里没有对应物。它也不碰三处必须字面一致的 `timeX` 正则。

## markdown-fmt-runner

在 Markdown 里敲 `///fmt` 再回车，删掉触发词与这次回车，保存文件，用当前文件路径调用 `_tool_fmt_md.py`，跑完把磁盘结果换回编辑器。

它和高亮扩展没有共用状态：不发装饰、不碰 `timeX` 正则，所以拆成独立扩展没有层叠问题，可以单独禁用。它的名称、命令 ID、设置项前缀都刻意不带项目名（`markdownFmt.*`），挪到别的仓库也能直接用——脚本路径默认是相对路径 `_tool_fmt_md.py`，按工作区根目录解析。

实现细节、踩过的坑和已知边界都写在 `markdown-fmt-runner/README.md` 里。要点三条：

- 触发判断放在**​回车​**而不是最后一个字符上。逐键上报的 `change.text` 一次只有一个字符，拿它跟整串比永远不成立。

- 删除范围必须**​覆盖这次回车​**，否则残留的换行会和原有空行凑成三连空行，被脚本当成场景分隔处理。

- 进程退出后**​主动读盘回填​**，不能只依赖文件监视器；回填前检查 `doc.isDirty`，避免吞掉排版期间的新输入。

