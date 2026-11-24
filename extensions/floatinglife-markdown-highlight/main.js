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

// ### 最近输入高亮（瞬态）：每次文档改动插入的文字染色 TYPED_TTL_MS。
// 按输入事件记账：一次键入或一次输入法上屏是一个事件，同一事件写入的字符共用到期时间。
const TYPED_TEXT_COLOR = '#BF8FFF';
const TYPED_TTL_MS = 7000;
const TYPED_MIN_TICK_MS = 50;        // 到期定时器最短间隔，避免同一时刻的条目让定时器空转
const TYPED_MAX_INSERT_CHARS = 2000; // 单次插入超过此长度视为粘贴，不产生新条目

// 击键只重置计时器，停手 REFRESH_DEBOUNCE_MS 后才真正重扫一次。
const REFRESH_DEBOUNCE_MS = 150;
let pendingRefresh = null;

// 静态规则的区间缓存：uri -> 每条 RULE 一个 [{start,end}] 数组，与装饰同步、随编辑平移。
// 有缓存才能在每次击键时重新切分静态区间（挖掉最近输入的部分）。
const staticByDoc = new Map();

// 最近输入的区间：uri -> [{start,end,expireAt}]。
const typedByDoc = new Map();

let typedDecoration = null;
let typedExpiryTimer = null;

// ---- 区间平移 ----

// 按一次改动平移「静态」区间。
// 与瞬态区间的关键区别：纯插入落在区间内部时，静态区间要把新字也包进来（整段仍是橙色），
// 不能像瞬态那样拆成前后两段——否则 7 秒后会在原处留下一道没有颜色的缺口。
function transformStaticRange(range, change) {
  const o = change.rangeOffset;
  const removed = change.rangeLength;
  const inserted = change.text.length;
  const oEnd = o + removed;
  const delta = inserted - removed;

  if (range.end <= o) return [range];                      // 改动在区间之后
  if (range.start >= oEnd) {                               // 改动在区间之前（含左端插入）
    return [{ start: range.start + delta, end: range.end + delta }];
  }
  if (range.start < o) {
    if (range.end <= oEnd) return [{ start: range.start, end: o }];
    return [{ start: range.start, end: range.end + delta }];
  }
  // 区间起点落在被替换区里：起点映射到插入文本末尾
  const start = o + inserted;
  const end = range.end >= oEnd ? range.end + delta : o + inserted;
  return end > start ? [{ start, end }] : [];
}

function applyStaticChanges(ranges, changes) {
  // 与瞬态区间同一套顺序规则：contentChanges 按 rangeOffset 降序、坐标以改动前为准。
  const sorted = [...changes].sort((a, b) => b.rangeOffset - a.rangeOffset);
  let current = ranges;
  for (const change of sorted) {
    const next = [];
    for (const r of current) {
      for (const piece of transformStaticRange(r, change)) next.push(piece);
    }
    current = next;
  }
  return current;
}

// 按一次改动平移一个「瞬态」条目。
// change 的 rangeOffset / rangeLength 是「改动前」文档坐标；调用方保证按 rangeOffset 降序处理。
function transformTypedEntry(entry, change) {
  const r = change.rangeOffset;
  const removed = change.rangeLength;
  const inserted = change.text.length;
  const rEnd = r + removed;
  const delta = inserted - removed;

  // 整条在改动点之前：不动。光标正好停在 entry.end 处的普通打字走的就是这条。
  if (entry.end <= r) return [entry];

  // 整条在改动点之后：整体平移。
  if (entry.start >= rEnd) {
    return [{ start: entry.start + delta, end: entry.end + delta, expireAt: entry.expireAt }];
  }

  // 与改动相交：只保留被替换区之外、仍然存在的旧字符。
  // 新插入的文字由调用方另记条目，这里不把旧条目抻长，否则过期时间会被带偏。
  const pieces = [];
  if (entry.start < r) {
    pieces.push({ start: entry.start, end: r, expireAt: entry.expireAt });
  }
  if (entry.end > rEnd) {
    pieces.push({ start: r + inserted, end: entry.end + delta, expireAt: entry.expireAt });
  }
  return pieces;
}

function applyTypedChanges(entries, changes) {
  // VS Code 按 rangeOffset 降序给出改动，且坐标都以改动前的文档为准。
  // 从大到小处理时，高处改动不会影响低处改动的坐标，比较始终有效。
  const sorted = [...changes].sort((a, b) => b.rangeOffset - a.rangeOffset);
  let current = entries;
  for (const change of sorted) {
    const next = [];
    for (const entry of current) {
      for (const piece of transformTypedEntry(entry, change)) next.push(piece);
    }
    current = next;
  }
  return current;
}

// 新插入的区间要换算到「改动后」的坐标：按升序累加更低位置改动的长度差。
function insertedTypedEntries(changes, expireAt) {
  const out = [];
  let shift = 0;
  for (const ch of [...changes].sort((a, b) => a.rangeOffset - b.rangeOffset)) {
    if (ch.text.length > 0 && ch.text.length <= TYPED_MAX_INSERT_CHARS) {
      out.push({
        start: ch.rangeOffset + shift,
        end: ch.rangeOffset + shift + ch.text.length,
        expireAt,
      });
    }
    shift += ch.text.length - ch.rangeLength;
  }
  return out;
}

// 从静态区间里挖掉最近输入的区间。
// 这是整套方案的关键：同一段文字只落进一种装饰，紫色能不能显示就不再取决于
// VS Code 的装饰层叠顺序（跨扩展时那个顺序既不是按类型创建顺序、也不是按设值顺序，两种都试过）。
function subtractTyped(ranges, typed) {
  if (!typed.length) return ranges;
  const cuts = [...typed].sort((a, b) => a.start - b.start);
  const out = [];
  for (const r of ranges) {
    let cur = r.start;
    for (const c of cuts) {
      if (c.end <= cur) continue;
      if (c.start >= r.end) break;
      if (c.start > cur) out.push({ start: cur, end: c.start });
      cur = Math.max(cur, c.end);
      if (cur >= r.end) break;
    }
    if (cur < r.end) out.push({ start: cur, end: r.end });
  }
  return out;
}

// 偏移数组 -> vscode.Range 数组。偏移失效（后台被外部改写）时跳过，等下一次全文重扫。
function offsetsToRanges(doc, list) {
  const out = [];
  for (const r of list) {
    if (r.end <= r.start) continue;
    try {
      out.push(new vscode.Range(doc.positionAt(r.start), doc.positionAt(r.end)));
    } catch {
      // 忽略，TTL 与重扫会兜底
    }
  }
  return out;
}

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

  function ensureTypedDecoration() {
    if (!typedDecoration) {
      typedDecoration = vscode.window.createTextEditorDecorationType({
        color: TYPED_TEXT_COLOR,
        rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
      });
    }
    return typedDecoration;
  }

  // 全文重扫一遍，把每条规则的区间存进缓存。
  function scanDocument(doc) {
    const text = doc.getText();
    const perRule = [];
    for (const rule of RULES) {
      const ranges = [];
      rule.regex.lastIndex = 0;
      let m;
      while ((m = rule.regex.exec(text))) {
        for (const [s, e] of rule.select(m)) {
          if (e > s) ranges.push({ start: s, end: e });
        }
      }
      perRule.push(ranges);
    }
    staticByDoc.set(doc.uri.toString(), perRule);
    return perRule;
  }

  function applyDecorations(editor) {
    const doc = editor.document;
    if (doc.languageId !== 'markdown') {
      for (const dec of decorations.values()) {
        editor.setDecorations(dec, []);
      }
      if (typedDecoration) editor.setDecorations(typedDecoration, []);
      return;
    }
    const key = doc.uri.toString();
    const perRule = staticByDoc.get(key) || RULES.map(() => []);
    const typed = typedByDoc.get(key) || [];
    for (let i = 0; i < RULES.length; i++) {
      const ranges = subtractTyped(perRule[i], typed);
      editor.setDecorations(decorations.get(RULES[i]), offsetsToRanges(doc, ranges));
    }
    if (typedDecoration) {
      editor.setDecorations(typedDecoration, offsetsToRanges(doc, typed));
    }
  }

  function refresh() {
    if (!activeEditor) return;
    const doc = activeEditor.document;
    if (doc.languageId === 'markdown') {
      scanDocument(doc);
    }
    // 同一文档可能在分屏里有两个编辑器，都要重绘
    for (const editor of vscode.window.visibleTextEditors) {
      if (editor.document === doc) applyDecorations(editor);
    }
    if (!vscode.window.visibleTextEditors.includes(activeEditor)) {
      applyDecorations(activeEditor);
    }
  }

  function scheduleRefresh() {
    if (pendingRefresh) {
      clearTimeout(pendingRefresh);
    }
    pendingRefresh = setTimeout(() => {
      pendingRefresh = null;
      refresh();
    }, REFRESH_DEBOUNCE_MS);
  }

  // 一个自续的定时器，总是指向最早的到期点；被新条目刷新时就重算。
  function scheduleTypedExpiry() {
    if (typedExpiryTimer) {
      clearTimeout(typedExpiryTimer);
      typedExpiryTimer = null;
    }
    let earliest = Infinity;
    for (const entries of typedByDoc.values()) {
      for (const e of entries) {
        if (e.expireAt < earliest) earliest = e.expireAt;
      }
    }
    if (earliest === Infinity) return;
    typedExpiryTimer = setTimeout(atTypedExpiry, Math.max(TYPED_MIN_TICK_MS, earliest - Date.now()));
  }

  function atTypedExpiry() {
    typedExpiryTimer = null;
    const now = Date.now();
    for (const [key, entries] of typedByDoc) {
      const kept = entries.filter((e) => e.end > e.start && e.expireAt > now);
      if (kept.length) typedByDoc.set(key, kept);
      else typedByDoc.delete(key);
    }
    // 到期要把静态区间补回来，所以整段重绘，不只是清掉紫色
    for (const editor of vscode.window.visibleTextEditors) {
      if (editor.document.languageId === 'markdown') applyDecorations(editor);
    }
    scheduleTypedExpiry();
  }

  function handleDocumentChange(event) {
    const doc = event.document;
    if (doc.languageId !== 'markdown') return;

    const key = doc.uri.toString();

    // 1. 静态缓存跟着编辑平移。即使文档当前不可见也要做，否则缓存会漂。
    const perRule = staticByDoc.get(key);
    if (perRule) {
      for (let i = 0; i < perRule.length; i++) {
        perRule[i] = applyStaticChanges(perRule[i], event.contentChanges);
      }
    }

    const visible = vscode.window.visibleTextEditors.some((e) => e.document === doc);
    if (!visible && !typedByDoc.has(key) && !perRule) return;

    // 2. 瞬态条目
    const now = Date.now();
    let entries = applyTypedChanges(typedByDoc.get(key) || [], event.contentChanges);

    // 撤销 / 重做不是「打字」：只平移旧区间，不产生新条目，
    // 否则 Ctrl+Z 撤回的文字会立刻又紫一片，反而看不清撤到了哪里。
    // TextDocumentChangeReason 是 1.74 才有的 API，engines 写的是 ^1.70，故做存在性保护。
    const CR = vscode.TextDocumentChangeReason;
    const isUndoRedo = CR && (event.reason === CR.Undo || event.reason === CR.Redo);
    if (visible && !isUndoRedo) {
      ensureTypedDecoration();
      entries = entries.concat(insertedTypedEntries(event.contentChanges, now + TYPED_TTL_MS));
    }

    entries = entries.filter((e) => e.end > e.start && e.expireAt > now);
    if (entries.length) typedByDoc.set(key, entries);
    else typedByDoc.delete(key);

    // 3. 同步重绘：连续打字时任何「停手后才触发」的去抖计时器都永远不到点
    if (perRule || entries.length) {
      for (const editor of vscode.window.visibleTextEditors) {
        if (editor.document === doc) applyDecorations(editor);
      }
    }
    scheduleTypedExpiry();

    // 4. 停手后重扫，修正平移产生的漂移并发现新的匹配
    if (activeEditor && event.document === activeEditor.document) {
      scheduleRefresh();
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
    vscode.workspace.onDidChangeTextDocument(handleDocumentChange),
    vscode.window.onDidChangeVisibleTextEditors(() => {
      for (const editor of vscode.window.visibleTextEditors) {
        if (editor.document.languageId === 'markdown') applyDecorations(editor);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((document) => {
      const key = document.uri.toString();
      staticByDoc.delete(key);
      if (typedByDoc.delete(key)) scheduleTypedExpiry();
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
exports.deactivate = () => {
  if (pendingRefresh) {
    clearTimeout(pendingRefresh);
    pendingRefresh = null;
  }
  if (typedExpiryTimer) {
    clearTimeout(typedExpiryTimer);
    typedExpiryTimer = null;
  }
  staticByDoc.clear();
  typedByDoc.clear();
  if (typedDecoration) {
    typedDecoration.dispose();
    typedDecoration = null;
  }
};
