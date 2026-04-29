/**
 * code4u.ai VS Code Extension - Main Entry Point
 * Full-featured AI coding assistant with autocomplete, chat, and agent control
 */

import * as vscode from 'vscode';

let client: Code4uClient | null = null;
let statusBarItem: vscode.StatusBarItem;
let sentinelStatusBarItem: vscode.StatusBarItem;
let chatViewProvider: ChatViewProvider | null = null;
let inlineCompletionProvider: Code4uInlineCompletionProvider | null = null;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  console.log('code4u.ai extension activating...');
  
  const config = vscode.workspace.getConfiguration('code4u');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
  
  // Initialize client
  client = new Code4uClient(serverUrl);
  
  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.text = '$(zap) code4u.ai';
  statusBarItem.tooltip = 'Click for code4u.ai actions';
  statusBarItem.command = 'code4u.showQuickActions';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Sentinel lock status bar (hidden by default)
  sentinelStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 99);
  sentinelStatusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  context.subscriptions.push(sentinelStatusBarItem);
  
  // Chat view
  chatViewProvider = new ChatViewProvider(context.extensionUri, client);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('code4u.chatView', chatViewProvider)
  );
  
  // Inline completion provider
  inlineCompletionProvider = new Code4uInlineCompletionProvider(client);
  context.subscriptions.push(
    vscode.languages.registerInlineCompletionItemProvider(
      { pattern: '**' },
      inlineCompletionProvider
    )
  );
  
  // Register all commands
  registerCommands(context, client);
  
  // Auto-connect
  if (config.get<boolean>('autoConnect', true)) {
    try {
      await client.connect();
      updateStatusBar('connected');
    } catch (e) {
      updateStatusBar('disconnected');
    }
  }
  
  console.log('code4u.ai extension activated');
}

export function deactivate(): void {
  client?.disconnect();
}

function updateStatusBar(status: 'connected' | 'disconnected' | 'thinking') {
  switch (status) {
    case 'connected':
      statusBarItem.text = '$(zap) code4u.ai';
      statusBarItem.backgroundColor = undefined;
      break;
    case 'disconnected':
      statusBarItem.text = '$(zap) code4u.ai (offline)';
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      break;
    case 'thinking':
      statusBarItem.text = '$(sync~spin) code4u.ai';
      break;
  }
}

function registerCommands(context: vscode.ExtensionContext, client: Code4uClient) {
  // Quick actions menu
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.showQuickActions', async () => {
      const action = await vscode.window.showQuickPick([
        { label: '$(git-branch) Refactor', description: 'AI-powered refactoring', command: 'code4u.refactor' },
        { label: '$(code) Generate Code', description: 'Generate code from description', command: 'code4u.generate' },
        { label: '$(bug) Fix Bug', description: 'Analyze and fix bugs', command: 'code4u.fixBug' },
        { label: '$(comment-discussion) Explain', description: 'Explain selected code', command: 'code4u.explain' },
        { label: '$(search) Analyze Impact', description: 'Analyze change impact', command: 'code4u.analyzeImpact' },
        { label: '$(symbol-method) Rename Symbol', description: 'Smart rename across codebase', command: 'code4u.renameSymbol' },
        { label: '$(comment) Open Chat', description: 'Open agent chat panel', command: 'code4u.openChat' },
        { label: '$(plug) Connect', description: 'Connect to code4u.ai server', command: 'code4u.connect' },
      ], { placeHolder: 'Select an action' });
      if (action) vscode.commands.executeCommand(action.command);
    })
  );

  // Connect
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.connect', async () => {
      try {
        await client.connect();
        updateStatusBar('connected');
        vscode.window.showInformationMessage('Connected to code4u.ai');
      } catch (e) {
        updateStatusBar('disconnected');
        vscode.window.showErrorMessage(`Failed to connect: ${e}`);
      }
    })
  );

  // Refactor
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.refactor', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
      }

      const intent = await vscode.window.showInputBox({
        prompt: 'What would you like to refactor?',
        placeHolder: 'e.g., Extract this to a separate module, rename email to primaryEmail',
      });
      if (!intent) return;

      updateStatusBar('thinking');
      
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'code4u.ai: Analyzing codebase...',
        cancellable: true,
      }, async (progress) => {
        progress.report({ message: 'Building Knowledge Graph...' });
        
        const result = await client.refactor({
          intent,
          filePath: editor.document.uri.fsPath,
          selection: editor.selection.isEmpty ? undefined : {
            start: editor.selection.start.line,
            end: editor.selection.end.line,
          },
          context: {
            language: editor.document.languageId,
            selectedText: editor.selection.isEmpty ? undefined : editor.document.getText(editor.selection),
          },
        });

        updateStatusBar('connected');

        if (result) {
          const breakingBadge = result.breakingChange ? '⚠️ BREAKING CHANGE\n\n' : '';
          const action = await vscode.window.showInformationMessage(
            `${breakingBadge}${result.analysis}\n\nAffects ${result.affectedFiles.length} files.`,
            'View Diff',
            'Accept',
            'Reject'
          );

          if (action === 'View Diff') {
            await showDiffView(result.diffs);
          } else if (action === 'Accept') {
            await client.acceptChanges();
            vscode.window.showInformationMessage('Changes applied successfully!');
          } else if (action === 'Reject') {
            await client.rejectChanges();
          }
        }
      });
    })
  );

  // Generate code
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.generate', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const description = await vscode.window.showInputBox({
        prompt: 'What code would you like to generate?',
        placeHolder: 'e.g., Create a REST API endpoint for user preferences',
      });
      if (!description) return;

      updateStatusBar('thinking');
      
      const result = await client.generate({
        description,
        filePath: editor.document.uri.fsPath,
        language: editor.document.languageId,
        cursorPosition: editor.selection.active.line,
      });

      updateStatusBar('connected');

      if (result?.code) {
        const position = editor.selection.active;
        await editor.edit(editBuilder => {
          editBuilder.insert(position, result.code);
        });
      }
    })
  );

  // Fix bug
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.fixBug', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const bugDescription = await vscode.window.showInputBox({
        prompt: 'Describe the bug',
        placeHolder: 'e.g., Function returns undefined when input is empty',
      });
      if (!bugDescription) return;

      updateStatusBar('thinking');
      
      const result = await client.fixBug({
        description: bugDescription,
        filePath: editor.document.uri.fsPath,
        selectedCode: editor.document.getText(editor.selection),
      });

      updateStatusBar('connected');

      if (result) {
        const action = await vscode.window.showInformationMessage(
          `Found issue: ${result.analysis}\n\nProposed fix ready.`,
          'Apply Fix',
          'Cancel'
        );
        if (action === 'Apply Fix') {
          await client.acceptChanges();
        }
      }
    })
  );

  // Explain
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.explain', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Please select code to explain');
        return;
      }

      updateStatusBar('thinking');
      
      const result = await client.explain({
        code: editor.document.getText(editor.selection),
        filePath: editor.document.uri.fsPath,
        language: editor.document.languageId,
      });

      updateStatusBar('connected');

      if (result?.explanation) {
        // Show in output channel
        const channel = vscode.window.createOutputChannel('code4u.ai Explanation');
        channel.clear();
        channel.appendLine(result.explanation);
        channel.show();
      }
    })
  );

  // Analyze impact
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.analyzeImpact', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      updateStatusBar('thinking');
      
      const result = await client.analyzeImpact(editor.document.uri.fsPath);
      
      updateStatusBar('connected');

      if (result) {
        const panel = vscode.window.createWebviewPanel(
          'code4uImpact',
          'Impact Analysis',
          vscode.ViewColumn.Beside,
          {}
        );
        panel.webview.html = getImpactAnalysisHtml(result);
      }
    })
  );

  // Show ownership
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.showOwnership', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const ownership = await client.getOwnership(editor.document.uri.fsPath);
      if (ownership) {
        vscode.window.showInformationMessage(
          `Owned by: ${ownership.teams.map((t: any) => t.name).join(', ')}`
        );
      }
    })
  );

  // Rename symbol
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.renameSymbol', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const wordRange = editor.document.getWordRangeAtPosition(editor.selection.active);
      const oldName = wordRange ? editor.document.getText(wordRange) : undefined;
      if (!oldName) {
        vscode.window.showWarningMessage('No symbol at cursor');
        return;
      }

      const newName = await vscode.window.showInputBox({
        prompt: `Rename '${oldName}' to:`,
        value: oldName,
      });
      if (!newName || newName === oldName) return;

      updateStatusBar('thinking');
      
      const result = await client.renameSymbol(oldName, newName, editor.document.uri.fsPath);
      
      updateStatusBar('connected');

      if (result) {
        const action = await vscode.window.showInformationMessage(
          `Will rename in ${result.affectedFiles.length} files. ${result.breakingChange ? '⚠️ Breaking change!' : ''}`,
          'Apply',
          'Cancel'
        );
        if (action === 'Apply') {
          await client.acceptChanges();
          vscode.window.showInformationMessage('Symbol renamed successfully');
        }
      }
    })
  );

  // Open chat
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.openChat', () => {
      vscode.commands.executeCommand('code4u.chatView.focus');
    })
  );

  // Accept/Reject/Rollback
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.acceptChanges', async () => {
      const result = await client.acceptChanges();
      if (result?.success) {
        vscode.window.showInformationMessage(`Applied ${result.changesApplied} changes`);
      }
    }),
    vscode.commands.registerCommand('code4u.rejectChanges', async () => {
      await client.rejectChanges();
      vscode.window.showInformationMessage('Changes rejected');
    }),
    vscode.commands.registerCommand('code4u.rollback', async () => {
      const result = await client.rollback();
      if (result?.success) {
        vscode.window.showInformationMessage('Changes rolled back');
      }
    })
  );

  // Refactor Symbol (right-click context menu — grabs symbol under cursor)
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.refactorSymbol', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
      }

      const wordRange = editor.document.getWordRangeAtPosition(editor.selection.active);
      const symbolName = wordRange ? editor.document.getText(wordRange) : undefined;
      if (!symbolName) {
        vscode.window.showWarningMessage('No symbol at cursor position');
        return;
      }

      const intent = await vscode.window.showInputBox({
        prompt: `Refactor '${symbolName}' — describe what you want:`,
        placeHolder: `e.g., Rename ${symbolName} to newName, Extract ${symbolName} to utils.py`,
        value: `Rename ${symbolName} to `,
      });
      if (!intent) return;

      const filePath = editor.document.uri.fsPath;
      const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
      const outputChannel = vscode.window.createOutputChannel('code4u.ai Refactor');
      outputChannel.show(true);
      outputChannel.appendLine(`[code4u] Intent: ${intent}`);
      outputChannel.appendLine(`[code4u] Symbol: ${symbolName}`);
      outputChannel.appendLine(`[code4u] File:   ${filePath}`);
      outputChannel.appendLine(`[code4u] Root:   ${workspacePath}`);
      outputChannel.appendLine('');

      updateStatusBar('thinking');

      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `code4u: Refactoring '${symbolName}'...`,
        cancellable: false,
      }, async (progress) => {
        try {
          progress.report({ message: 'Creating job...' });
          const job = await client.createRefactorJob(intent, filePath, workspacePath);
          if (!job?.jobId) {
            vscode.window.showErrorMessage('Failed to create refactor job');
            updateStatusBar('connected');
            return;
          }
          outputChannel.appendLine(`[code4u] Job created: ${job.jobId}`);

          progress.report({ message: 'Connecting to live event stream...' });
          const result = await client.streamJob(job.jobId, (event: any) => {
            const msg = event.message || event.type || '';
            progress.report({ message: msg });
            outputChannel.appendLine(`[code4u] ${event.type}: ${msg}`);

            if (event.type === 'diff' && event.file) {
              outputChannel.appendLine(`  [diff] ${event.action ?? 'edit'} ${event.file}`);
            }
            if (event.type === 'generate_complete' && event.affectedFiles) {
              outputChannel.appendLine(`  [files] ${event.affectedFiles.join(', ')}`);
            }
          });

          updateStatusBar('connected');

          if (result?.status === 'APPLIED' || result?.status === 'DIFF_PREVIEWED') {
            outputChannel.appendLine(`\n[code4u] Pipeline completed: ${result.status}`);
            outputChannel.appendLine(`[code4u] Affected files: ${result.affectedFiles?.length ?? 0}`);

            if (result.diffs) {
              for (const [fp, diff] of Object.entries(result.diffs as Record<string, string>)) {
                outputChannel.appendLine(`\n--- ${fp} ---`);
                outputChannel.appendLine(diff);
              }
            }

            const action = await vscode.window.showInformationMessage(
              `Refactor complete — ${result.affectedFiles?.length ?? 0} file(s) affected.`,
              'View Diffs', 'OK'
            );
            if (action === 'View Diffs' && result.diffs) {
              await showDiffView(Object.entries(result.diffs as Record<string, string>).map(
                ([fp, content]) => ({ filePath: fp, content })
              ));
            }
          } else {
            outputChannel.appendLine(`\n[code4u] Pipeline ended: ${result?.status ?? 'unknown'}`);
            if (result?.error) {
              outputChannel.appendLine(`[code4u] Error: ${result.error}`);
            }
            vscode.window.showErrorMessage(`Refactor failed: ${result?.error ?? result?.status}`);
          }
        } catch (e: any) {
          if (e.statusCode === 409 || e.message?.includes('409')) {
            await handleConflict(workspacePath, outputChannel);
          } else {
            outputChannel.appendLine(`[code4u] Error: ${e.message ?? e}`);
            vscode.window.showErrorMessage(`Refactor error: ${e.message ?? e}`);
          }
        }
        updateStatusBar('connected');
      });
    })
  );

  // Health Check
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.healthCheck', async () => {
      const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspacePath) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
      }

      const outputChannel = vscode.window.createOutputChannel('code4u.ai Health');
      outputChannel.show(true);
      outputChannel.appendLine(`[code4u] Running health check on: ${workspacePath}`);

      updateStatusBar('thinking');

      try {
        const indexResult = await client.indexWorkspace(workspacePath);
        outputChannel.appendLine(`[code4u] Indexed ${indexResult?.stats?.indexed_files ?? '?'} files`);
        outputChannel.appendLine(`[code4u] Symbols: ${indexResult?.stats?.total_symbols ?? '?'}`);
        outputChannel.appendLine(`[code4u] Imports: ${indexResult?.stats?.total_imports ?? '?'}`);
        outputChannel.appendLine(`[code4u] Cache hits: ${indexResult?.stats?.cache_hits ?? '?'}`);
        outputChannel.appendLine('');

        const cyclesResult = await client.detectCycles(workspacePath);
        const cycleCount = cyclesResult?.cycles?.length ?? 0;
        if (cycleCount > 0) {
          outputChannel.appendLine(`[code4u] WARNING: ${cycleCount} circular import chain(s) detected:`);
          for (const cycle of cyclesResult.cycles) {
            outputChannel.appendLine(`  ${cycle.join(' -> ')}`);
          }
        } else {
          outputChannel.appendLine('[code4u] No circular dependencies found.');
        }

        vscode.window.showInformationMessage(
          `Health: ${indexResult?.stats?.indexed_files ?? '?'} files, ` +
          `${indexResult?.stats?.total_symbols ?? '?'} symbols, ` +
          `${cycleCount} cycle(s)`
        );
      } catch (e: any) {
        outputChannel.appendLine(`[code4u] Error: ${e.message ?? e}`);
        vscode.window.showErrorMessage(`Health check failed: ${e.message ?? e}`);
      }

      updateStatusBar('connected');
    })
  );

  // Toggle inline completion
  context.subscriptions.push(
    vscode.commands.registerCommand('code4u.toggleAutocomplete', () => {
      const config = vscode.workspace.getConfiguration('code4u');
      const current = config.get<boolean>('enableAutocomplete', true);
      config.update('enableAutocomplete', !current, true);
      vscode.window.showInformationMessage(`Autocomplete ${!current ? 'enabled' : 'disabled'}`);
    })
  );
}

async function handleConflict(workspacePath: string, outputChannel: vscode.OutputChannel) {
  try {
    const sentinel = await client?.getSentinelStatus(workspacePath);
    const owningSession = sentinel?.owningSession || 'unknown';
    const msg = `Workspace is locked by session [${owningSession}]. Another refactor is in progress.`;
    outputChannel.appendLine(`[code4u] CONFLICT: ${msg}`);
    vscode.window.showWarningMessage(`$(lock) ${msg}`, 'Retry Later');

    sentinelStatusBarItem.text = `$(lock) Workspace locked (${owningSession.substring(0, 8)}...)`;
    sentinelStatusBarItem.tooltip = `Workspace locked by session ${owningSession}. Wait for the current refactor to finish.`;
    sentinelStatusBarItem.show();

    setTimeout(() => sentinelStatusBarItem.hide(), 30000);
  } catch {
    vscode.window.showWarningMessage('Workspace is currently locked by another refactor. Please wait.');
  }
}

async function showDiffView(diffs: any[]) {
  // Create a diff view for the changes
  const panel = vscode.window.createWebviewPanel(
    'code4uDiff',
    'code4u.ai Changes',
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  panel.webview.html = getDiffViewHtml(diffs);
}

function getDiffViewHtml(diffs: any[]): string {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: var(--vscode-font-family); padding: 20px; }
    .diff-file { margin-bottom: 20px; }
    .diff-header { background: var(--vscode-editor-background); padding: 10px; border-radius: 4px; }
    .diff-content { font-family: monospace; white-space: pre; }
    .add { background: rgba(0, 255, 0, 0.1); color: #22c55e; }
    .remove { background: rgba(255, 0, 0, 0.1); color: #ef4444; }
  </style>
</head>
<body>
  <h2>Proposed Changes</h2>
  ${diffs.map(d => `
    <div class="diff-file">
      <div class="diff-header">${d.filePath}</div>
      <div class="diff-content">${d.content || 'No changes'}</div>
    </div>
  `).join('')}
</body>
</html>`;
}

function getImpactAnalysisHtml(result: any): string {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: var(--vscode-font-family); padding: 20px; }
    .stat { display: inline-block; margin-right: 20px; padding: 10px 15px; background: var(--vscode-editor-background); border-radius: 8px; }
    .stat-value { font-size: 24px; font-weight: bold; }
    .stat-label { font-size: 12px; opacity: 0.7; }
    .file-list { margin-top: 20px; }
    .file { padding: 8px; border-bottom: 1px solid var(--vscode-widget-border); }
  </style>
</head>
<body>
  <h2>Impact Analysis</h2>
  <div>
    <div class="stat"><div class="stat-value">${result.blastRadius?.repositories || 0}</div><div class="stat-label">Repositories</div></div>
    <div class="stat"><div class="stat-value">${result.blastRadius?.teams || 0}</div><div class="stat-label">Teams</div></div>
    <div class="stat"><div class="stat-value">${result.affectedFiles?.length || 0}</div><div class="stat-label">Files</div></div>
  </div>
  ${result.breakingChange ? '<p style="color: #f59e0b; font-weight: bold;">⚠️ This is a breaking change</p>' : ''}
  <div class="file-list">
    <h3>Affected Files</h3>
    ${(result.affectedFiles || []).map((f: string) => `<div class="file">${f}</div>`).join('')}
  </div>
</body>
</html>`;
}

// Chat View Provider
class ChatViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _client: Code4uClient
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };
    webviewView.webview.html = this._getHtml();
    webviewView.webview.onDidReceiveMessage(async (data) => {
      if (data.type === 'send') {
        const response = await this._client.chat(data.message);
        webviewView.webview.postMessage({ type: 'response', content: response.message });
      }
    });
  }

  private _getHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: var(--vscode-font-family); padding: 10px; margin: 0; display: flex; flex-direction: column; height: 100vh; }
    .messages { flex: 1; overflow-y: auto; }
    .message { margin-bottom: 10px; padding: 8px; border-radius: 8px; }
    .user { background: var(--vscode-button-background); color: var(--vscode-button-foreground); margin-left: 20%; }
    .agent { background: var(--vscode-editor-background); margin-right: 20%; }
    .input-area { display: flex; gap: 8px; padding-top: 10px; border-top: 1px solid var(--vscode-widget-border); }
    input { flex: 1; padding: 8px; border: 1px solid var(--vscode-input-border); background: var(--vscode-input-background); color: var(--vscode-input-foreground); border-radius: 4px; }
    button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
  </style>
</head>
<body>
  <div class="messages" id="messages"></div>
  <div class="input-area">
    <input type="text" id="input" placeholder="Ask the agent..." />
    <button onclick="send()">Send</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');
    
    function send() {
      const text = input.value.trim();
      if (!text) return;
      addMessage(text, 'user');
      vscode.postMessage({ type: 'send', message: text });
      input.value = '';
    }
    
    function addMessage(text, role) {
      const div = document.createElement('div');
      div.className = 'message ' + role;
      div.textContent = text;
      messages.appendChild(div);
      messages.scrollTop = messages.scrollHeight;
    }
    
    input.addEventListener('keypress', (e) => { if (e.key === 'Enter') send(); });
    
    window.addEventListener('message', (e) => {
      if (e.data.type === 'response') addMessage(e.data.content, 'agent');
    });
  </script>
</body>
</html>`;
  }
}

// Inline Completion Provider
class Code4uInlineCompletionProvider implements vscode.InlineCompletionItemProvider {
  constructor(private readonly _client: Code4uClient) {}

  async provideInlineCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    context: vscode.InlineCompletionContext,
    token: vscode.CancellationToken
  ): Promise<vscode.InlineCompletionItem[] | vscode.InlineCompletionList | null> {
    const config = vscode.workspace.getConfiguration('code4u');
    if (!config.get<boolean>('enableAutocomplete', true)) {
      return null;
    }

    // Get context
    const linePrefix = document.lineAt(position.line).text.substring(0, position.character);
    const textBefore = document.getText(new vscode.Range(
      new vscode.Position(Math.max(0, position.line - 50), 0),
      position
    ));

    try {
      const result = await this._client.complete({
        prefix: textBefore,
        suffix: document.getText(new vscode.Range(
          position,
          new vscode.Position(Math.min(document.lineCount - 1, position.line + 10), 0)
        )),
        language: document.languageId,
        filePath: document.uri.fsPath,
      });

      if (result?.completion) {
        return [
          new vscode.InlineCompletionItem(
            result.completion,
            new vscode.Range(position, position)
          ),
        ];
      }
    } catch (e) {
      // Silently fail
    }

    return null;
  }
}

// API Client
class Code4uClient {
  private connected = false;
  private ws: WebSocket | null = null;

  constructor(private serverUrl: string) {}

  async connect(): Promise<void> {
    // Try HTTP health check
    const response = await fetch(`${this.serverUrl}/health`);
    if (response.ok) {
      this.connected = true;
    } else {
      throw new Error('Server not available');
    }
  }

  disconnect(): void {
    this.connected = false;
    this.ws?.close();
  }

  async refactor(req: any): Promise<any> {
    return this.post('/api/v1/refactor', req);
  }

  async generate(req: any): Promise<any> {
    return this.post('/api/v1/generate', req);
  }

  async fixBug(req: any): Promise<any> {
    return this.post('/api/v1/fix-bug', req);
  }

  async explain(req: any): Promise<any> {
    return this.post('/api/v1/explain', req);
  }

  async complete(req: any): Promise<any> {
    return this.post('/api/v1/autocomplete/inline', req);
  }

  async chat(message: string): Promise<any> {
    return this.post('/api/v1/chat', { message });
  }

  async analyzeImpact(filePath: string): Promise<any> {
    return this.post('/api/v1/analysis/impact', { filePath });
  }

  async getOwnership(filePath: string): Promise<any> {
    return this.post('/api/v1/analysis/ownership', { filePath });
  }

  async renameSymbol(oldName: string, newName: string, filePath: string): Promise<any> {
    return this.post('/api/v1/refactor/rename', { oldName, newName, filePath });
  }

  async acceptChanges(): Promise<any> {
    return this.post('/api/v1/transactions/accept', {});
  }

  async rejectChanges(): Promise<any> {
    return this.post('/api/v1/transactions/reject', {});
  }

  async rollback(): Promise<any> {
    return this.post('/api/v1/transactions/rollback', {});
  }

  async createRefactorJob(intent: string, filePath: string, workspacePath: string): Promise<any> {
    return this.post('/api/v1/refactor/rename/jobs', {
      intent,
      filePath,
      workspacePath,
    });
  }

  async pollJob(jobId: string, onStatus?: (status: string) => void): Promise<any> {
    const maxAttempts = 60;
    const intervalMs = 1000;
    for (let i = 0; i < maxAttempts; i++) {
      const result = await this.get(`/api/v1/refactor/jobs/${jobId}`);
      const state = result?.currentState ?? result?.status ?? '';
      if (onStatus) onStatus(state);
      if (['APPLIED', 'DIFF_PREVIEWED', 'FAILED'].includes(state)) {
        return { ...result, status: state };
      }
      await new Promise(r => setTimeout(r, intervalMs));
    }
    return { status: 'TIMEOUT', error: 'Job timed out after 60s' };
  }

  async streamJob(jobId: string, onEvent?: (event: any) => void): Promise<any> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);

    try {
      const response = await fetch(`${this.serverUrl}/api/v1/events/${jobId}`, {
        signal: controller.signal,
        headers: { 'Accept': 'text/event-stream' },
      });

      if (!response.ok || !response.body) {
        return this.pollJob(jobId, onEvent ? (s: string) => onEvent({ type: 'poll', message: s }) : undefined);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              if (onEvent) onEvent(event);
              if (event.type === 'pipeline_complete' || event.type === 'pipeline_error') {
                clearTimeout(timeout);
                const result = await this.get(`/api/v1/refactor/jobs/${jobId}`);
                const state = result?.currentState ?? result?.status ?? '';
                return { ...result, status: state };
              }
            } catch {}
          }
        }
      }
    } catch {
      // SSE not available, fall back to polling
    }

    clearTimeout(timeout);
    return this.pollJob(jobId, onEvent ? (s: string) => onEvent({ type: 'poll', message: s }) : undefined);
  }

  async getSentinelStatus(workspacePath: string): Promise<any> {
    return this.get(`/api/v1/refactor/sentinel/status?workspace=${encodeURIComponent(workspacePath)}`);
  }

  async indexWorkspace(workspacePath: string): Promise<any> {
    return this.post('/api/v1/refactor/index', { workspacePath });
  }

  async detectCycles(workspacePath: string): Promise<any> {
    return this.get(`/api/v1/refactor/index/cycles?workspace=${encodeURIComponent(workspacePath)}`);
  }

  private async post(path: string, body: any): Promise<any> {
    const response = await fetch(`${this.serverUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return response.json();
  }

  private async get(path: string): Promise<any> {
    const response = await fetch(`${this.serverUrl}${path}`);
    return response.json();
  }
}
