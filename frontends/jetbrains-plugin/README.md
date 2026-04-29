# code4u.ai JetBrains Plugin

The official code4u.ai plugin for JetBrains IDEs (IntelliJ IDEA, WebStorm, PyCharm, etc.).

## Features

### 🚀 Intelligent Autocomplete
- Context-aware code suggestions powered by Knowledge Graph
- Multi-file understanding
- Language-specific optimizations

### ⌨️ Tab Completion (Inline Suggestions)
- Multi-line ghost text completions
- Tab to accept, Escape to dismiss
- Smart rewrites as you type

### 🤖 Agent Mode
- Delegate coding tasks with natural language
- Deterministic state machine execution
- Human-in-the-loop approval

### 🔧 Refactoring
- Safe, validated refactors across your codebase
- Impact analysis before changes
- Automatic rollback on failure

### 📊 Impact Analysis
- See what files and symbols will be affected
- Breaking change detection
- Ownership boundary awareness

## Installation

### From JetBrains Marketplace
1. Open your JetBrains IDE
2. Go to `Settings/Preferences` → `Plugins`
3. Search for "code4u.ai"
4. Click `Install`

### Manual Installation
1. Download the latest `.zip` from [Releases](https://github.com/code4u-ai/jetbrains-plugin/releases)
2. Go to `Settings/Preferences` → `Plugins`
3. Click the gear icon → `Install Plugin from Disk...`
4. Select the downloaded `.zip` file

## Configuration

Go to `Settings/Preferences` → `Tools` → `code4u.ai`

### Connection
- **Server URL**: Your code4u.ai backend URL (default: `http://localhost:8002`)
- **API Key**: Your API key from the code4u.ai dashboard
- **Tenant ID**: Your organization's tenant ID

### Autocomplete
- **Enable Autocomplete**: Toggle code completions
- **Enable Inline Completion (Tab)**: Toggle ghost text suggestions
- **Trigger Delay**: Milliseconds before showing completions
- **Max Completions**: Number of suggestions to show

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Refactor with code4u | `Ctrl+Alt+R` | `⌘⌥R` |
| Explain Code | `Ctrl+Alt+E` | `⌘⌥E` |
| Generate Code | `Ctrl+Alt+G` | `⌘⌥G` |
| Open Agent Chat | `Ctrl+Alt+C` | `⌘⌥C` |
| Toggle Autocomplete | `Ctrl+Alt+A` | `⌘⌥A` |

## Usage

### Autocomplete
Simply start typing and code4u.ai will suggest completions. Use:
- `↑/↓` to navigate suggestions
- `Enter` or `Tab` to accept
- `Escape` to dismiss

### Tab Completion (Ghost Text)
As you type, code4u.ai shows ghost text predictions:
- `Tab` to accept the entire suggestion
- `Escape` to dismiss
- Continue typing to refine

### Refactoring
1. Select code or place cursor on a symbol
2. Press `Ctrl+Alt+R` (or right-click → "Refactor with code4u")
3. Describe your intent
4. Review the proposed changes
5. Apply or reject

### Agent Chat
1. Press `Ctrl+Alt+C` to open the chat panel
2. Describe what you want to do
3. The agent will analyze, plan, and execute
4. Review changes before they're applied

## Building from Source

```bash
# Clone the repository
git clone https://github.com/code4u-ai/jetbrains-plugin.git
cd jetbrains-plugin

# Build
./gradlew build

# Run in a sandboxed IDE
./gradlew runIde

# Package for distribution
./gradlew buildPlugin
```

## Requirements

- JetBrains IDE 2023.3 or later
- code4u.ai backend running (self-hosted or cloud)

## Enterprise Features

For enterprise users:
- **SSO Integration**: SAML/OIDC support
- **Tenant Isolation**: Per-organization data separation
- **No-AI Zones**: Exclude sensitive files from AI processing
- **Audit Logs**: Complete audit trail of all operations
- **Self-Hosted**: Run entirely on your infrastructure

## Support

- 📚 [Documentation](https://docs.code4u.ai)
- 💬 [Discord Community](https://discord.gg/code4u)
- 📧 [Email Support](mailto:support@code4u.ai)
- 🐛 [Issue Tracker](https://github.com/code4u-ai/jetbrains-plugin/issues)

## License

Copyright © 2026 code4u.ai. All rights reserved.

