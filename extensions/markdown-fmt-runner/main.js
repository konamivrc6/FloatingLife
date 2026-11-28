const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const vscode = require('vscode');

// 默认用相对路径：按「当前文件所在的工作区根目录」解析，换机器、换盘符都不用改设置。
const DEFAULT_SCRIPT_PATH = '_tool_fmt_md.py';
const DEFAULT_TRIGGER = '///fmt';
const DEFAULT_PYTHON = 'python';

// 排版一整部长篇小说（148 KB）实测约 0.7 s；60 s 还跑不完只可能是参数写错，让脚本退化成了递归模式。
const RUN_TIMEOUT_MS = 60000;

const CONFIG_SECTION = 'markdownFmt';
const COMMAND_ID = 'markdownFmt.formatFile';

// 一次回车的插入内容：换行，加可选的自动缩进 / 列表符号 / 引用号。用来把「按了回车」和「粘贴了东西」分开，
// 只有前者才允许连同插入内容一起删掉。
const ENTER_INSERT = /^[\r\n]+[ \t]*(?:[-*+][ \t]+|\d+\.[ \t]+|>)?$/;

// ---- 设置 ----

function getSettings() {
  const cfg = vscode.workspace.getConfiguration(CONFIG_SECTION);
  const trigger = String(cfg.get('trigger', DEFAULT_TRIGGER) || '');
  return {
    enabled: cfg.get('enabled', true),
    trigger: trigger.length ? trigger : DEFAULT_TRIGGER,
    scriptPath: cfg.get('scriptPath', DEFAULT_SCRIPT_PATH) || DEFAULT_SCRIPT_PATH,
    pythonPath: cfg.get('pythonPath', DEFAULT_PYTHON) || DEFAULT_PYTHON,
  };
}

// ---- 触发词识别 ----

// 在本次改动里找「敲 ///fmt 再回车」的命中，返回 { start, end, expected }（改动后的文档坐标）。
//
// 判据只有三条：这次改动是一次回车、回车前那一段正好是触发词、不在代码块里。只看光标左侧，
// 不必猜用户敲到第几个字符。删除范围覆盖整次插入（触发词 + 回车及其自动缩进），否则残留的换行
// 会和原有空行凑成 \n\n\n，排版工具会把它当成三连空行，插出一段 <br/>。
function findTriggerHit(doc, changes, trigger) {
  // 一次回车会插入换行，以及编辑器自动补的缩进或列表符号（在列表里回车得到的是 "\n- "）。
  // 这些都属于「这一次回车」，删的时候要一并撤掉。
  if (!changes.some((c) => ENTER_INSERT.test(c.text))) return null;

  const text = doc.getText();
  // contentChanges 的坐标以改动前为准、按 rangeOffset 降序给出；升序累加长度差换算到改动后。
  const sorted = [...changes].sort((a, b) => a.rangeOffset - b.rangeOffset);
  let shift = 0;
  let hit = null;
  for (const change of sorted) {
    if (ENTER_INSERT.test(change.text)) {
      const start = change.rangeOffset + shift; // 换行在改动后的偏移
      if (start >= trigger.length && text.slice(start - trigger.length, start) === trigger) {
        hit = {
          start: start - trigger.length,
          end: start + change.text.length,
          expected: trigger + change.text,
        };
      }
    }
    shift += change.text.length - change.rangeLength;
  }
  return hit;
}

// 判断 offset 是否落在 fenced 代码块内。规则按 CommonMark 近似：
// 开栏是行首（可缩进 0-3）连续 3 个以上 ` 或 ~，且反引号开栏的 info string 里不能再出现反引号；
// 闭栏必须同字符、不短于开栏，且后面只剩空白。未闭合的开栏视为一直延续到文末。
function isInsideFence(text, offset) {
  let open = null;
  for (const line of text.slice(0, offset).split('\n')) {
    const m = /^[ \t]{0,3}(`{3,}|~{3,})(.*)$/.exec(line);
    if (!m) continue;
    const run = m[1];
    const rest = m[2];
    if (!open) {
      if (run[0] === '`' && rest.includes('`')) continue;
      open = { ch: run[0], len: run.length };
    } else if (run[0] === open.ch && run.length >= open.len && rest.trim() === '') {
      open = null;
    }
  }
  return open !== null;
}

// 定位脚本：绝对路径直接用；相对路径先按「当前文件所在的工作区根目录」拼，
// 没开工作区（单独打开一个文件）时再从文档所在目录逐级向上找。都找不到返回 null。
function resolveScriptPath(configured, doc) {
  if (path.isAbsolute(configured)) {
    return fs.existsSync(configured) ? configured : null;
  }

  const roots = [];
  const folder = vscode.workspace.getWorkspaceFolder(doc.uri);
  if (folder) roots.push(folder.uri.fsPath);

  let dir = path.dirname(doc.uri.fsPath);
  for (let i = 0; i < 8; i += 1) {
    roots.push(dir);
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  for (const root of roots) {
    const candidate = path.join(root, configured);
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

// ---- 扩展主体 ----

function activate(context) {
  const output = vscode.window.createOutputChannel('Markdown 排版');
  // 同一文件不允许并发：第一次排版还没结束时，第二次触发直接忽略，否则两个进程会互相覆盖写盘。
  const running = new Set();
  // 自己发起的编辑不参与触发检测（删触发词、回填排版结果都会产生改动事件）。
  let internalEdits = 0;
  let child = null;

  function internalEdit(fn) {
    internalEdits += 1;
    return Promise.resolve()
      .then(fn)
      .finally(() => {
        internalEdits -= 1;
      });
  }

  function showError(message, ...actions) {
    vscode.window.showErrorMessage(`Markdown 排版：${message}`, ...actions).then((choice) => {
      if (choice === '查看输出') output.show(true);
      else if (choice === '打开设置') {
        vscode.commands.executeCommand('workbench.action.openSettings', CONFIG_SECTION);
      }
    });
  }

  // 跑脚本，把 stdout/stderr 实时灌进输出面板，返回 { code, stdout, timedOut, spawnError }。
  function runScript(settings, scriptPath, filePath) {
    return new Promise((resolve) => {
      output.appendLine(`──── ${new Date().toLocaleTimeString()}  排版 ${path.basename(filePath)}`);

      let proc;
      try {
        proc = spawn(settings.pythonPath, [scriptPath, filePath], {
          // 脚本按 __file__ 推算仓库根，CWD 其实无关紧要；设成脚本所在目录只为让相对路径的日志更好读。
          cwd: path.dirname(scriptPath),
          windowsHide: true,
          // 管道重定向时 Python 3.14 的 stdout 走 locale 编码（本机 cp936），不强制 UTF-8 中文会变成乱码。
          env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
        });
      } catch (err) {
        output.appendLine(`启动失败：${err.message}`);
        resolve({ code: null, stdout: '', spawnError: err });
        return;
      }

      child = proc;
      let stdout = '';
      let timedOut = false;
      let spawnError = null;
      const timer = setTimeout(() => {
        timedOut = true;
        proc.kill();
      }, RUN_TIMEOUT_MS);

      const collect = (buf) => {
        const text = buf.toString('utf8');
        stdout += text;
        output.append(text);
      };
      proc.stdout.on('data', collect);
      proc.stderr.on('data', collect);
      proc.on('error', (err) => {
        spawnError = err;
        output.appendLine(`无法启动「${settings.pythonPath}」：${err.message}`);
      });
      proc.on('close', (code) => {
        clearTimeout(timer);
        child = null;
        output.appendLine(`──── 退出码 ${code}${timedOut ? '（超时终止）' : ''}`);
        resolve({ code, stdout, timedOut, spawnError });
      });
    });
  }

  // 把排版结果整体换进编辑器。撤销栈里是一步，Ctrl+Z 能一次撤回。
  async function replaceWholeDocument(editor, next) {
    const doc = editor.document;
    const before = doc.getText();
    if (before === next) return;

    // 排版只改动空白，按字符偏移回位基本对得上；positionAt 会自行夹到文末。
    const cursor = Math.min(doc.offsetAt(editor.selection.active), before.length);
    const full = new vscode.Range(doc.positionAt(0), doc.positionAt(before.length));
    await internalEdit(() => editor.edit((builder) => builder.replace(full, next)));
    const pos = doc.positionAt(Math.min(cursor, doc.getText().length));
    editor.selection = new vscode.Selection(pos, pos);
  }

  async function formatDocument(editor, hit) {
    const doc = editor.document;
    const settings = getSettings();
    const key = doc.uri.toString();

    if (running.has(key)) {
      vscode.window.setStatusBarMessage('Markdown 排版：上一次排版还没结束，已忽略', 3000);
      return;
    }
    if (doc.isUntitled) {
      showError('未命名文件没有磁盘路径，无法排版');
      return;
    }
    const scriptPath = resolveScriptPath(settings.scriptPath, doc);
    if (!scriptPath) {
      showError(`找不到脚本「${settings.scriptPath}」：工作区根目录和当前文件的上级目录里都没有`, '打开设置');
      return;
    }

    running.add(key);
    try {
      // 1. 先删触发词和这次回车，否则它们会被写进文件，多出来的空行还会被脚本当成三连空行。
      if (hit) {
        const range = new vscode.Range(doc.positionAt(hit.start), doc.positionAt(hit.end));
        await internalEdit(() => editor.edit((builder) => builder.delete(range)));
      }

      // 2. 保存。脚本读写的是磁盘，缓冲区里没保存的字它看不见。
      const saved = await doc.save();
      if (!saved) {
        showError('保存失败，未执行排版');
        return;
      }

      // 3. 运行脚本。
      const result = await runScript(settings, scriptPath, doc.uri.fsPath);
      if (result.timedOut) {
        showError(`排版超时（${RUN_TIMEOUT_MS / 1000} 秒），已终止`, '查看输出');
        return;
      }
      if (result.spawnError) {
        showError(`无法启动「${settings.pythonPath}」：${result.spawnError.message}`, '打开设置');
        return;
      }
      if (result.code !== 0) {
        showError(`脚本退出码 ${result.code}，详见输出面板`, '查看输出');
        return;
      }
      if (result.stdout.includes('命中忽略规则')) {
        vscode.window.showWarningMessage('Markdown 排版：该文件命中 .toolignore 规则，脚本跳过了它。');
        return;
      }

      // 4. 把磁盘结果同步回缓冲区。
      // 不能只指望 VS Code 的文件监视器：它可能已经自动 reload（内容自然一致），也可能还没轮到。
      let disk = null;
      try {
        disk = fs.readFileSync(doc.uri.fsPath, 'utf8');
        // VS Code 读文件时会剥掉 BOM，TextDocument 里没有它；这里也剥掉，否则比对永远不等，
        // 一保存就把 BOM 写进正文。
        if (disk.charCodeAt(0) === 0xfeff) disk = disk.slice(1);
      } catch {
        // 读不回来就交给监视器，不是致命错误
      }
      if (disk !== null && !doc.isClosed && disk !== doc.getText()) {
        if (doc.isDirty) {
          // 排版那零点几秒里用户又敲了字：磁盘上已经是被排版过的版本，此时覆盖会吞掉新输入。
          vscode.window.showWarningMessage(
            'Markdown 排版：排版期间文件又被改动过，没有自动覆盖编辑器内容。磁盘上已是排版后的版本，请手动重新加载该文件。'
          );
        } else {
          await replaceWholeDocument(editor, disk);
        }
      }

      const noChange = result.stdout.includes('No changes');
      vscode.window.setStatusBarMessage(
        noChange ? 'Markdown 排版：无改动' : `Markdown 排版：已排版 ${path.basename(doc.uri.fsPath)}`,
        4000
      );
    } catch (err) {
      showError(`${err && err.message ? err.message : err}`, '查看输出');
      output.appendLine(String((err && err.stack) || err));
    } finally {
      running.delete(key);
    }
  }

  function onDidChangeTextDocument(event) {
    if (internalEdits > 0) return;
    const settings = getSettings();
    if (!settings.enabled) return;

    const doc = event.document;
    if (doc.languageId !== 'markdown' || doc.uri.scheme !== 'file') return;

    const hit = findTriggerHit(doc, event.contentChanges, settings.trigger);
    if (!hit) return;

    // 代码块里的 ///fmt 多半是正文或示例，不当作命令。这一步要取全文，所以只在命中触发词后才做。
    if (isInsideFence(doc.getText(), hit.start)) return;

    const editor = vscode.window.visibleTextEditors.find((e) => e.document === doc);
    if (!editor) return;

    const expected = new vscode.Range(doc.positionAt(hit.start), doc.positionAt(hit.end));
    // 改文档事件里不当场发起编辑，推到下一轮事件循环再动手，免得和正在应用的这次改动打架。
    setTimeout(() => {
      if (doc.isClosed) return;
      // 推迟期间可能又有输入，偏移会失效；确认那段文字仍然原样在才继续。
      let stillThere = false;
      try {
        stillThere = doc.getText(expected) === hit.expected;
      } catch {
        // 文档变短后旧区间越界，当作没命中
      }
      if (stillThere) void formatDocument(editor, hit);
    }, 0);
  }

  context.subscriptions.push(
    output,
    // activate 的返回值 VS Code 不会当成 Disposable，退出时杀子进程得自己挂进 subscriptions。
    new vscode.Disposable(() => {
      if (child) {
        child.kill();
        child = null;
      }
    }),
    vscode.workspace.onDidChangeTextDocument(onDidChangeTextDocument),
    vscode.commands.registerCommand(COMMAND_ID, async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      if (editor.document.languageId !== 'markdown') {
        vscode.window.showWarningMessage('Markdown 排版：当前文件不是 Markdown。');
        return;
      }
      await formatDocument(editor, null);
    })
  );
}

exports.activate = activate;
exports.deactivate = () => {};
