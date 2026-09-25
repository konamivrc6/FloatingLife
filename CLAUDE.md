# CLAUDE.md

个人中文长篇小说《浮生 · 满梧》的写作仓库。正文、设定、大纲全部是 Markdown；仓库附带一套 Python 静态站点构建脚本、一批文稿处理工具，和一个自用的 VS Code 高亮扩展。

## 硬性约定

**不要手动折行。** 提交信息、文档、正文、代码注释一律如此——一行就是一行，多长都不手动断开。Markdown 靠软换行渲染，手动折行会变成真的换行；要分段就空一行。这条没有例外。

## 目录地图

**手写源文件**（改内容只改这些）

| 路径 | 内容 |
|---|---|
| `浮生 · 满梧.md` | 正文 |
| `浮生 · 满梧_toWrite.md` | 大纲 / 待写清单 / 事件卡，编号与正文平行 |
| `TimeLine.md` | 时间线对照表，是 `timeX` 标签取值的权威表 |
| `Clipboard.md` | 自定义标记速查表 |
| `[WLD] Worldbuilding Bureau/` | 世界观设定集，文件名 `N 标题.md` |
| `[CHR] Personnel Archives/` | 人物档案 |
| `[RES] Fact-check Dept/` | 现实考据资料（可查证的真实资料，不是虚拟机构） |
| `[TMP] Drafts/` | 草稿池 |
| `20260522 从此停止使用docx记录内容/` | 已迁移的 docx 归档，仅存档 |

**派生物**（不要手改；`.gitignore` + `.toolignore` 双重忽略）
`*_Original.md`（工具自动备份）、`*_colored.md`（PDF 导出用副本）、`*_LLM.md`、`temp*`

**构建产物**：`docs/` —— 由 CI 重建，纯产物，永远不要手改。

## 内容规则

### 章节格式是硬约束

`## N 标题`：行首、半角数字、数字后**必须**跟一个半角空格。`build.py` 用 `^## (\d+)\s+(.+?)$` 切章，格式错了整章会被吞进上一章。章号从 **0** 起，且必须连续——上下章导航按 `num ± 1` 查表，跳号会断链。

全文只有一个 `# 浮生`（书名）。**不要在正文里加第二个 `#`**：`_tool_fix_chapters.py` 支持按 `#` 分节独立编号，但 `build.py` 不支持，会让 `## 0` 撞号。

### 自定义标记

| 标记 | 说明 |
|---|---|
| `/* … */` | 作者注 / 伏笔备忘，可跨行。**构建时被 `strip_comments()` 删干净**，不会发布 |
| `### 标题_timeX_完成` | **只在大纲文件里是语法**（文件名含 `_toWrite` 才被处理，正文里不写这个语法）。标题文字里不能有 `_` |
| `timeX` | `X` 支持负数和小数（`time0` / `time0.5` / `time-1`）。取值去 `TimeLine.md` 对表 |
| `“ ”` | 人物口语 |
| `「 」` | 屏幕 / 聊天 / 系统界面文字。**这两个渠道不要混用** |
| `*斜体*` | UI 标签、屏幕显示文字、读音——**不是内心独白** |
| `<br>` | 表格单元格内换行（手写，能存活） |
| `<br/>` | 由 `_tool_fmt_md.py` 生成。**不要手写**，会被删掉再重生（fenced 代码块内的除外，那里不处理） |
| 全角空格 `　` | 单据 / 标识牌内的对齐间距 |
| `$…$` | 数学公式；构建期不处理，浏览器里由 KaTeX（jsdelivr CDN）渲染 |

颜色高亮**不是**手写语法：`<span style="color:…">` 由 `_tool_export_colored.py` 扫描生成，只出现在 `_colored.md` 里，不要手写进正文。

### 排版与标点

`_tool_fmt_md.py` 是格式的唯一权威，它强制：全角引号、中英文之间插空格、数字与单位插空格（白名单单位）、`......` → `……`、4 个以上 `-` → `——`、`*` 内侧插零宽空格、单体 `_` 转义为 `\_`、3 连空行展开成 `<br/>` 段。**改排版请用它，不要手改这些细节**——手改会与它冲突。

以上全部**只在 fenced 代码块之外生效**：每个行首围栏块（``` / ~~~，含围栏行本身与 info string）在管线开始前被整体遮成一个哨兵字符，跑完逐字还原，代码块内容逐字节不动。行内 `` `code` `` 与 `$…$` 数学**不**在这个保护范围内，仍会被排版。已知边界：围栏必须位于行首（可缩进），`> ``` ` 这类嵌在引用块里的围栏识别不到；未闭合的围栏也不遮蔽。唯一仍全局生效的是行尾统一 LF（`\r` 被当作文件卫生而非排版）。

## 构建与发布

```bash
python build.py    # 无参数、无子命令；依赖 markdown 库；产出 docs/
```

- 只能从**仓库根目录**运行。
- 只读三处输入：`浮生 · 满梧.md`、`[WLD] Worldbuilding Bureau/*.md`（不递归）、`static/fonts/`。**不读** `[CHR]` / `[RES]` / `[TMP]`。
- `docs/style.css` 和 `docs/theme.js` 是从 `build.py` 里的字符串常量生成的——**改样式要改 build.py**，直接编辑 `docs/` 无效。
- 全量重建，无增量：`build()` 开头就 `shutil.rmtree(docs/)` 整个删掉再重建，所以已删除的章节/设定不会留下旧 HTML。
- 构建非确定性：首页星空 SVG 用了无种子的 `random`，每次产物都不同。
- 部署：push 到 **`main`** 触发 GitHub Actions（`.github/workflows/deploy.yml`）→ `pip install markdown && python build.py` → 上传 `docs/` 制品到 GitHub Pages。**只有 `main` 会触发部署**，推 `drafting` 等分支不会，必须先合到 `main`。
- `浮生 · 满梧_toWrite.md` 含 `#` 分节和重号，**不能直接构建**，须先整理成连续的正文格式。

## 工具脚本

全部从**仓库根目录**运行（多个脚本按 CWD 递归），全部交互式，没有 `--dry-run` / `--yes`。

| 脚本 | 作用 |
|---|---|
| `_tool_fix_chapters.py <文件...>` | 章节序号重排；文件名含 `_toWrite` 时额外做 `###` 标签规范化与排序 |
| `_tool_fmt_md.py [文件...]` | 排版标准化（见上）。**无参数则递归整个仓库**，`-all` 递归整个仓库且跳过确认。fenced 代码块内容原样保留 |
| `_tool_export_colored.py <文件...>` | 生成 `X_colored.md` 供 PDF 导出，原文件只读 |
| `_tool_count_words.pyw` | 字数统计 CLI（用法见下）；统计前会剥掉作者注 / HTML 标签 / 标题行的 `#` 与序号 / 零宽空格 |
| `_tool_gen_random_int.pyw` | tkinter 随机数（空格键切本福特定律分布） |
| `_tool_strip_bom.py` | 递归去 `.txt/.py/.md` 的 UTF-8 BOM |
| `_tool_clean_backups.py` | 删除所有 `*_Original*` 备份 |
| `_tool_clear_drafts.py` | 清空 `temp*.md` |

`_tool_count_words.pyw` 的 CLI 用法：`python _tool_count_words.pyw <文件.md>` → 打印 5 项字数（字符数 / 汉字无标点 / 汉字含标点 / 西文词数 / 含标点字数），退出码 0；缺参数则打印用法、退出码 1。按 `utf-8-sig` 读文件，带 BOM 的源文件也能用。

`含标点字数` 的口径是 **汉字 + 中文标点 + 西文词数**，走字符制。**它不是官方稿酬口径**——《使用文字作品支付报酬办法》算的是版面字数（排印的版面每行字数 × 全部实有行数），与字号开本绑定，纯文本还原不出来。两者结构不同，别拿这个数直接对稿酬。西文按**词数**计（`Hello` 与 `internationalization` 同价），不按字符折算。

### ⚠️ 破坏性脚本

- **`_tool_clear_drafts.py` 的确认步骤被注释掉了**——无提示、不可逆、无备份地清空 `temp*.md`。而 `[TMP] Drafts/` 里可能存着真实草稿。**运行前先自己备份。**
- `_tool_clean_backups.py` 永久删除所有 `_Original` 备份，无备份。
- `_tool_fmt_md.py` 无参数时**原地重写当前目录下所有 `.md`**，只问一次且回车即继续；`-all` 连这一次也跳过，直接动手。它改的不只是排版（还会全角化引号、插入空格和零宽空格）。fenced 代码块内容不受影响。
- `_tool_fix_chapters.py` 最规矩：先打印完整报告 → 要 `y` → 备份 `X_Original.md` → 才写回。

### `.toolignore` 机制

`_lib/toolignore.py` + `.toolignore` 决定"这批工具该不该处理某个文件"，按 basename 做 glob，防止误加工派生物：`*_Original*`、`*_colored*`、`*_LLM*`、`*Clipboard*`、`temp*`、`README.md`。`build.py` 也读它。它与 `.gitignore` 是两套并行的规则。

### 必须同步的三处

`timeX` 正则在三个文件里各写了一份，**必须保持字面一致**：
`extensions/floatinglife-markdown-highlight/main.js`、`_tool_fix_chapters.py`、`_tool_export_colored.py`。

同理高亮色表在 `main.js` 和 `_tool_export_colored.py` 里各一份，且**刻意有两处差异**：导出时不染引号/书名号（正文里引号太密，全染上会太扎眼），`timeX` 改深金 `#B8860B`（`#E5C07B` 在白纸上看不见）。

## 命名约定

- `·`（两侧带空格）：主标题 / 副标题，如 `浮生 · 满梧.md`
- `_`：后缀标识，**一律用 `_`**，不用 `-` 或 `()`。文件级 `_toWrite` / `_Original` / `_colored` / `_LLM`；行内标签 `_time0` / `_完成` / `_丢弃`
- `[]`：只用于四个分类目录名，格式 `[三字母大写] 英文机构名`（方括号让它们排在文件列表最前）
- 设定集文件名 `N 标题.md`（数字 + 半角空格）；`build.py` 靠这个解析序号，无编号者垫底、序号显示为 `^`
- 标点一律全角

## 其他

- `floating life MC save.zip` 是 Minecraft 存档，用来校对小说场景的空间描写一致性。
- VS Code 扩展 `extensions/floatinglife-markdown-highlight`：用 decoration 给标记上色，纯视觉不改文件。**不是语法注入**——`extensions/README.md` 记录了语法注入在本机反复失灵的教训，不要改回语法注入。打包用 `python extensions/pack_vsix.py`（不需要 vsce/node），装完要**完整重启** VS Code（不是 Reload Window）。
- 提交信息用 Conventional Commits + scope：`feat(tool):` / `fix(build):` / `docs(prose):` / `perf(ext):` / `refactor:`。正文用 `-` 逐条展开，一条一行、不手动折行。
- 仓库有外部贡献者通过 PR 提交（编号写在标题尾部，如 `(#35)`）。
