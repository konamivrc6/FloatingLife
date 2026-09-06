# Markdown 高亮（FloatingLife Markdown Highlight）

在 VS Code 里编辑 Markdown 时，给常用的一些文字上色：

| 内容 | 颜色 | 默认值 |
|---|---|---|
| `/* ... */` 块注释 | 绿 | `#4caf50` |
| 中文双引号 `“ ”` | 橙 | `#DA893B` |
| 直角引号 `「 」` | 橙 | `#DA893B` |
| 书名号 `《 》` | 橙 | `#DA893B` |
| `###` 标题的时间标签 `timeX`（如 `_time0.5`、`_time-1`） | 黄 | `#E5C07B` |
| `###` 标题的状态标签 `丢弃` | 红 | `#E05561` |
| `###` 标题的状态标签 `完成` | 绿 | `#4CAF50` |
| `###` 标题的其他标签与分隔符 `_` | 灰 | `#808080` |

标题文字本身不动，保留 VS Code 默认 Markdown 标题样式；只有 `### ` 之后的标签区被染色。
扩展激活时用正则扫描文档，给匹配范围套上**装饰（decoration）**染色——不依赖语法注入，确定性生效，不受主题或 VS Code 版本影响。

## 安装

1. VS Code 里 `Ctrl+Shift+P` → `Extensions: Install from VSIX...`，选择打包好的 `.vsix` 文件。
2. **完整重启 VS Code**（关闭所有窗口再打开，不是 `Reload Window`）。

## 配置颜色（可选）

默认绿注释 + 橙引号/书名号。想改，打开设置（`Ctrl+,` → 右上角 JSON 图标），加：

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

- 只在 **Markdown** 文件里生效（`onLanguage:markdown` 激活）。
- 引号/书名号**整段染色**（含前后标点）；**只有前引号、没有后引号时不染色**（正则要求成对出现）。
- 纯视觉染色，不修改文件内容，不影响编译、搜索、其他语法高亮。
