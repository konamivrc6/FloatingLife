const vscode = require('vscode');

// 高亮规则。regex 需带 /g；select(m) 返回要染色的 [起始偏移, 结束偏移]。
const RULES = [
  {
    configKey: 'blockCommentColor',
    defaultColor: '#4caf50',
    // C/C++ 风格块注释，整个 /* ... */ 都染色
    regex: /\/\*[\s\S]*?\*\//g,
    select: (m) => [m.index, m.index + m[0].length],
  },
  {
    configKey: 'quoteColor',
    defaultColor: '#DA893B',
    // 中文双引号“”、直角引号「」、书名号《》，整段（含前后标点）染色
    regex: /“[^”]+”|「[^」]+」|《[^》]+》/g,
    select: (m) => [m.index, m.index + m[0].length],
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
        const [s, e] = rule.select(m);
        ranges.push(
          new vscode.Range(
            editor.document.positionAt(s),
            editor.document.positionAt(e)
          )
        );
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
