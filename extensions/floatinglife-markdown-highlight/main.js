const vscode = require('vscode');

// ### 标题标签：timeX（黄）、丢弃（红）、完成（绿）、其他标签与 _（灰）
const TIME_TAG_RE = /^time-?\d+(?:\.\d+)?$/;   // 与 _tool_fix_chapters.py 一致
const H3_TAG_RE = /^### .*?(_[^\n]*)$/gm;      // ### 标题行，组 1 = 从第一个 _ 起的标签区

// 把 H3_TAG_RE 匹配出的标签区按 kind 拆成若干 [s,e] 区间（不重叠；不为该 kind 时返回空数组）。
function tagPairs(m, kind) {
  const region = m[1];                          // 以 _ 开头
  const base = m.index + m[0].length - region.length;
  const out = [];
  let i = 0;
  while (i < region.length) {
    if (region[i] === '_') {
      if (kind === 'other') out.push([base + i, base + i + 1]);
      i += 1;
      continue;
    }
    const tokStart = i;
    while (i < region.length && region[i] !== '_') i += 1;
    const tok = region.slice(tokStart, i);
    const isTime = TIME_TAG_RE.test(tok);
    const isDiscard = tok === '丢弃';
    const isDone = tok === '完成';
    if (
      (kind === 'time' && isTime) ||
      (kind === 'discard' && isDiscard) ||
      (kind === 'done' && isDone) ||
      (kind === 'other' && !isTime && !isDiscard && !isDone)
    ) {
      out.push([base + tokStart, base + i]);
    }
  }
  return out;
}

// 高亮规则。regex 需带 /g；select(m) 返回要染色的 [起始, 结束] 偏移数组（可为空数组）。
const RULES = [
  {
    configKey: 'blockCommentColor',
    defaultColor: '#4caf50',
    // C/C++ 风格块注释，整个 /* ... */ 都染色
    regex: /\/\*[\s\S]*?\*\//g,
    select: (m) => [[m.index, m.index + m[0].length]],
  },
  {
    configKey: 'quoteColor',
    defaultColor: '#DA893B',
    // 中文双引号“”、直角引号「」、书名号《》，整段（含前后标点）染色
    regex: /“[^”]+”|「[^」]+」|《[^》]+》/g,
    select: (m) => [[m.index, m.index + m[0].length]],
  },
  {
    configKey: 'timeTagColor',
    defaultColor: '#E5C07B', // 黄
    // ### 标题里的时间标签 timeX（含小数/负数）
    regex: H3_TAG_RE,
    select: (m) => tagPairs(m, 'time'),
  },
  {
    configKey: 'discardTagColor',
    defaultColor: '#E05561', // 红
    regex: H3_TAG_RE,
    select: (m) => tagPairs(m, 'discard'),
  },
  {
    configKey: 'doneTagColor',
    defaultColor: '#4CAF50', // 绿
    regex: H3_TAG_RE,
    select: (m) => tagPairs(m, 'done'),
  },
  {
    configKey: 'otherTagColor',
    defaultColor: '#808080', // 灰
    // 其他标签与每个分隔 _
    regex: H3_TAG_RE,
    select: (m) => tagPairs(m, 'other'),
  },
];

function activate(context) {
  let activeEditor = vscode.window.activeTextEditor;

  function ruleColor(rule) {
    return vscode.workspace
      .getConfiguration('floatinglifeHighlight')
      .get(rule.configKey, rule.defaultColor);
  }

  function makeDecoration(rule) {
    return vscode.window.createTextEditorDecorationType({
      color: ruleColor(rule),
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
    });
  }

  const decorations = new Map(RULES.map((r) => [r, makeDecoration(r)]));

  function updateDecorations(editor) {
    if (!editor) {
      return;
    }
    if (editor.document.languageId !== 'markdown') {
      for (const dec of decorations.values()) {
        editor.setDecorations(dec, []);
      }
      return;
    }
    const text = editor.document.getText();
    for (const rule of RULES) {
      const ranges = [];
      rule.regex.lastIndex = 0;
      let m;
      while ((m = rule.regex.exec(text))) {
        for (const [s, e] of rule.select(m)) {
          ranges.push(
            new vscode.Range(
              editor.document.positionAt(s),
              editor.document.positionAt(e)
            )
          );
        }
      }
      editor.setDecorations(decorations.get(rule), ranges);
    }
  }

  function refresh() {
    if (activeEditor) {
      updateDecorations(activeEditor);
    }
  }

  if (activeEditor) {
    refresh();
  }

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      activeEditor = editor;
      refresh();
    }),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (activeEditor && event.document === activeEditor.document) {
        refresh();
      }
    }),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('floatinglifeHighlight')) {
        for (const dec of decorations.values()) {
          dec.dispose();
        }
        decorations.clear();
        for (const r of RULES) {
          decorations.set(r, makeDecoration(r));
        }
        refresh();
      }
    })
  );
}

exports.activate = activate;
exports.deactivate = () => {};
