# Markdown 高亮（FloatingLife Markdown Highlight）

在 VS Code 里编辑 Markdown 时，给常用的一些文字上色：

| 内容 | 颜色 | 默认值 |
|---|---|---|
| `/* ... */` 块注释 | 绿 | `#4caf50` |
| 中文双引号 `“ ”` | 橙 | `#DA893 B` |
| 直角引号 `「 」` | 橙 | `#DA893 B` |
| 书名号 `《 》` | 橙 | `#DA893 B` |
| `###` 标题的时间标签 `timeX`（如 `_time0.5`、`_time-1`） | 黄 | `#E5C07 B` |
| `###` 标题的状态标签 `丢弃` | 红 | `#E05561` |
| `###` 标题的状态标签 `完成` | 绿 | `#4CAF50` |
| `###` 标题的其他标签与分隔符 `_` | 灰 | `#808080` |
| 最近 7 秒内输入的文字 | 紫 | `#BF8FFF`（固定，不可配置） |

标题文字本身不动，保留 VS Code 默认 Markdown 标题样式；只有 `### ` 之后的标签区被染色。

扩展激活时用正则扫描文档，给匹配范围套上**​装饰（decoration）​**染色——不依赖语法注入，确定性生效，不受主题或 VS Code 版本影响。

## 最近输入高亮

最近 7 秒内打进编辑器里的文字会染成紫色 `#BF8FFF`，到期后恢复原色；连续打字时形成一条逐段退色的尾巴。

- 按输入事件计时：一次键入或一次输入法上屏算一个事件，同一事件写进文档的字符共用一个 7 秒窗口。逐字输入时尾巴是逐字的，一次上屏一段时那段一起退色。

- 颜色和时长是固定常量，没有配置项；要改就改 `main.js` 顶部的 `TYPED_TEXT_COLOR` / `TYPED_TTL_MS`。

- 撤销 / 重做不会产生新的紫色；被撤销掉的文字立即失去紫色。

- 一次插入超过 2000 字符（大段粘贴）不染色，避免整章变紫。

- 与上面的静态高亮落在同一段文字上时，紫色优先：静态区间会先被「挖掉」最近输入的部分再分别染色，不依赖 VS Code 的装饰层叠顺序。

## 安装

1. VS Code 里 `Ctrl+Shift+P` → `Extensions: Install from VSIX...`，选择打包好的 `.vsix` 文件。

2. **​完整重启 VS Code​**（关闭所有窗口再打开，不是 `Reload Window`）。

## 配置颜色（可选）

默认绿注释 + 橙引号 / 书名号。想改，打开设置（`Ctrl+,` → 右上角 JSON 图标），加：

```jsonc
{
  "floatinglifeHighlight.blockCommentColor": "#6a9955",
  "floatinglifeHighlight.quoteColor": "#DA893B",
  "floatinglifeHighlight.timeTagColor": "#E5C07B",
  "floatinglifeHighlight.discardTagColor": "#E05561",
  "floatinglifeHighlight.doneTagColor": "#4CAF50",
  "floatinglifeHighlight.otherTagColor": "#808080"
}
```

改完后 `Developer: Reload Window` 生效。

## 说明

- 只在 **​Markdown​** 文件里生效（`onLanguage:markdown` 激活）。

- 引号 / 书名号**​整段染色​**（含前后标点）；**​只有前引号、没有后引号时不染色​**（正则要求成对出现）。

- 纯视觉染色，不修改文件内容，不影响编译、搜索、其他语法高亮。

