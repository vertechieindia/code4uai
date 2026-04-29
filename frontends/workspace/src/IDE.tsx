import { useState, useRef, useEffect, useCallback } from 'react'
import Editor, { OnMount } from '@monaco-editor/react'
import { useAuth } from './AuthContext'
import ChatMessage from './components/ChatMessage'
import {
  FolderOpen,
  File,
  ChevronRight,
  ChevronDown,
  Terminal as TerminalIcon,
  GitBranch,
  Send,
  Sparkles,
  X,
  Save,
  RefreshCw,
  FolderGit2,
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
  Loader2,
  AlertCircle,
  FolderInput,
  Network,
  Flame,
  Bug,
  AlertTriangle,
  XCircle,
  Info,
  TestTube2,
  CheckCircle2,
  Activity,
  Ticket,
  ExternalLink,
  Tag,
  Zap,
  Gauge,
  Search,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────

interface FileNode {
  name: string
  type: 'file' | 'folder'
  path: string
  language?: string
  children?: FileNode[]
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  code?: string
}

interface ExternalIssue {
  id: string
  key: string
  title: string
  description: string
  status: string
  priority: string
  type: string
  assignee: string
  labels: string[]
  url: string
  provider: string
}

// ── Helpers ──────────────────────────────────────────────────────

const API = '/api/v1'

function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

function langFromPath(p: string): string {
  const ext = p.split('.').pop()?.toLowerCase() || ''
  const m: Record<string, string> = {
    py: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript',
    jsx: 'javascript', json: 'json', md: 'markdown', css: 'css',
    html: 'html', yaml: 'yaml', yml: 'yaml', toml: 'toml',
    go: 'go', rs: 'rust', sh: 'shell', sql: 'sql',
  }
  return m[ext] || 'plaintext'
}

// ── Component ────────────────────────────────────────────────────

export default function IDE() {
  const { token } = useAuth()

  // Workspace path — defaults to the project root
  const [workspacePath, setWorkspacePath] = useState(() =>
    localStorage.getItem('code4u_workspace') || ''
  )
  const [showWorkspacePicker, setShowWorkspacePicker] = useState(!workspacePath)
  const [workspaceInput, setWorkspaceInput] = useState(workspacePath)

  // File tree
  const [files, setFiles] = useState<FileNode[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [treeError, setTreeError] = useState('')

  // Editor state
  const [openFiles, setOpenFiles] = useState<string[]>([])
  const [activeFile, setActiveFile] = useState<string>('')
  const [fileContents, setFileContents] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState<Set<string>>(new Set())
  const [editorLoading, setEditorLoading] = useState(false)

  // UI panels
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [showSidebar, setShowSidebar] = useState(true)
  const [showTerminal, setShowTerminal] = useState(true)
  const [showChat, setShowChat] = useState(true)
  const [showGraph, setShowGraph] = useState(false)

  // Knowledge Graph hot spots
  const [hotSpots, setHotSpots] = useState<Array<{name: string, kind: string, file: string, startLine: number, docstring: string}>>([])
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphStats, setGraphStats] = useState<{totalFiles: number, totalSymbols: number}>({totalFiles: 0, totalSymbols: 0})

  // Issues tab (architectural debt)
  const [showIssues, setShowIssues] = useState(false)
  const [issues, setIssues] = useState<Array<{
    filePath: string; line: number; category: string;
    severity: string; message: string; suggestion: string;
  }>>([])
  const [issuesLoading, setIssuesLoading] = useState(false)
  const [issuesScanned, setIssuesScanned] = useState(0)

  // Test runner
  const [testResult, setTestResult] = useState<{
    status: string; output: string; failedTests: string[];
    durationMs: number; framework: string; command: string;
  } | null>(null)
  const [testRunning, setTestRunning] = useState(false)

  // External issues (Jira/Linear/GitHub)
  const [showExtIssues, setShowExtIssues] = useState(false)
  const [extIssues, setExtIssues] = useState<ExternalIssue[]>([])
  const [extIssuesLoading, setExtIssuesLoading] = useState(false)
  const [extIssuesProvider, setExtIssuesProvider] = useState('')

  // Performance profiler
  const [showPerf, setShowPerf] = useState(false)
  const [perfResults, setPerfResults] = useState<Array<{
    filePath: string; smellCount: number; maxComplexity: number; lines: number;
    smells: Array<{ category: string; description: string; severity: string; line_number: number }>
  }>>([])
  const [perfLoading, setPerfLoading] = useState(false)

  // Semantic search
  const [semanticQuery, setSemanticQuery] = useState('')
  const [semanticResults, setSemanticResults] = useState<Array<{
    filePath: string; score: number; snippet: string; matchedLine: number; language: string
  }>>([])
  const [semanticSearching, setSemanticSearching] = useState(false)

  // Agent presence
  const [agentPresence, setAgentPresence] = useState<Array<{
    agent: string; file: string; line: number; action: string
  }>>([])
  const editorRef = useRef<any>(null)
  const monacoRef = useRef<any>(null)
  const decorationsRef = useRef<string[]>([])

  // Terminal
  const [terminalOutput, setTerminalOutput] = useState<string[]>(['$ Ready.'])
  const [terminalInput, setTerminalInput] = useState('')
  const [terminalRunning, setTerminalRunning] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)

  // Chat
  const [chatMessages, setChatMessages] = useState<Message[]>([
    { role: 'assistant', content: "Hi! I'm your AI assistant backed by the code4u Knowledge Graph. Ask me about your code." }
  ])
  const [chatInput, setChatInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const chatRef = useRef<HTMLDivElement>(null)

  // ── Workspace selection ──────────────────────────────────────

  const setWorkspace = (p: string) => {
    const clean = p.trim()
    setWorkspacePath(clean)
    localStorage.setItem('code4u_workspace', clean)
    setShowWorkspacePicker(false)
    setFiles([])
    setOpenFiles([])
    setActiveFile('')
    setFileContents({})
  }

  // ── Fetch file tree ──────────────────────────────────────────

  const fetchTree = useCallback(async () => {
    if (!workspacePath) return
    setTreeLoading(true)
    setTreeError('')
    try {
      const res = await fetch(`${API}/projects/files?path=${encodeURIComponent(workspacePath)}`, {
        headers: authHeaders(token),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to load files')
      const data = await res.json()
      setFiles(data.tree)
      // auto-expand top-level folders
      const topFolders = data.tree.filter((n: FileNode) => n.type === 'folder').map((n: FileNode) => n.path)
      setExpandedFolders(new Set(topFolders))
    } catch (e: any) {
      setTreeError(e.message)
    } finally {
      setTreeLoading(false)
    }
  }, [workspacePath, token])

  useEffect(() => { fetchTree() }, [fetchTree])

  // ── Fetch Knowledge Graph hot spots ───────────────────────────

  const fetchGraphHotSpots = useCallback(async () => {
    if (!workspacePath) return
    setGraphLoading(true)
    try {
      const res = await fetch(`${API}/symbols/definitions?workspace=${encodeURIComponent(workspacePath)}`, {
        headers: authHeaders(token),
      })
      if (!res.ok) return
      const data = await res.json()
      setGraphStats({ totalFiles: data.totalFiles || 0, totalSymbols: data.totalSymbols || 0 })
      const symbols = (data.symbols || []) as Array<{name: string, kind: string, file: string, startLine: number, docstring: string}>
      // Sort by "connectedness" — classes and functions first, then by name
      const sorted = symbols.sort((a, b) => {
        const kindOrder: Record<string, number> = { class: 0, function: 1, method: 2, variable: 3 }
        return (kindOrder[a.kind] ?? 4) - (kindOrder[b.kind] ?? 4)
      })
      setHotSpots(sorted.slice(0, 50))
    } catch {}
    setGraphLoading(false)
  }, [workspacePath, token])

  useEffect(() => {
    if (showGraph) fetchGraphHotSpots()
  }, [showGraph, fetchGraphHotSpots])

  // ── Fetch architectural issues (profiler scan) ────────────────

  const fetchIssues = useCallback(async () => {
    if (!workspacePath) return
    setIssuesLoading(true)
    setIssues([])
    setIssuesScanned(0)

    try {
      const res = await fetch(`${API}/projects/files?path=${encodeURIComponent(workspacePath)}`, {
        headers: authHeaders(token),
      })
      if (!res.ok) return
      const data = await res.json()

      const pyFiles: string[] = []
      const collectFiles = (nodes: FileNode[]) => {
        for (const n of nodes) {
          if (n.type === 'file' && n.name.endsWith('.py')) pyFiles.push(n.path)
          if (n.children) collectFiles(n.children)
        }
      }
      collectFiles(data.tree || [])

      const filesToScan = pyFiles.slice(0, 20)
      const allIssues: typeof issues = []

      for (const relPath of filesToScan) {
        try {
          const abs = workspacePath + '/' + relPath
          const contentRes = await fetch(`${API}/files/content?path=${encodeURIComponent(abs)}`, {
            headers: authHeaders(token),
          })
          if (!contentRes.ok) continue
          const { content } = await contentRes.json()
          if (!content) continue

          const scanRes = await fetch(`${API}/review/scan`, {
            method: 'POST',
            headers: authHeaders(token),
            body: JSON.stringify({ source: content, filePath: relPath }),
          })
          if (!scanRes.ok) continue
          const scanData = await scanRes.json()

          for (const note of scanData.notes || []) {
            allIssues.push(note)
          }
          setIssuesScanned(prev => prev + 1)
        } catch {}
      }

      if (allIssues.length === 0 && filesToScan.length > 0) {
        for (const relPath of filesToScan) {
          try {
            const abs = workspacePath + '/' + relPath
            const contentRes = await fetch(`${API}/files/content?path=${encodeURIComponent(abs)}`, {
              headers: authHeaders(token),
            })
            if (!contentRes.ok) continue
            const { content } = await contentRes.json()
            if (!content) continue

            const scanRes = await fetch(`${API}/profiler/scan`, {
              method: 'POST',
              headers: authHeaders(token),
              body: JSON.stringify({ source: content, filePath: relPath }),
            })
            if (!scanRes.ok) continue
            const scanData = await scanRes.json()
            for (const smell of scanData.smells || []) {
              allIssues.push({
                filePath: smell.filePath || relPath,
                line: smell.lineNumber || 0,
                category: `Performance: ${smell.category}`,
                severity: smell.severity || 'warning',
                message: smell.description || '',
                suggestion: '',
              })
            }
          } catch {}
        }
      }

      allIssues.sort((a, b) => {
        const sevOrder: Record<string, number> = { error: 0, warning: 1, info: 2 }
        return (sevOrder[a.severity] ?? 3) - (sevOrder[b.severity] ?? 3)
      })

      setIssues(allIssues)
    } catch {}
    setIssuesLoading(false)
  }, [workspacePath, token])

  useEffect(() => {
    if (showIssues) fetchIssues()
  }, [showIssues, fetchIssues])

  // ── Run tests ─────────────────────────────────────────────────

  const runTests = async () => {
    if (!workspacePath || testRunning) return
    setTestRunning(true)
    setTestResult(null)
    setTerminalOutput(prev => [...prev, '$ Running tests...'])

    try {
      const res = await fetch(`${API}/test/run`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ workspacePath }),
      })
      const data = await res.json()
      setTestResult(data)

      const lines: string[] = []
      lines.push(`[${data.framework}] ${data.command}`)
      if (data.output) lines.push(...data.output.split('\n'))
      lines.push(data.status === 'pass'
        ? `\u2705 Tests passed (${data.durationMs}ms)`
        : `\u274C Tests failed (${data.failedTests?.length || 0} failures, ${data.durationMs}ms)`)
      setTerminalOutput(prev => [...prev, ...lines])
    } catch {
      setTerminalOutput(prev => [...prev, 'Error: could not reach test runner'])
    } finally {
      setTestRunning(false)
    }
  }

  // ── Performance profiler scan ───────────────────────────────

  const fetchPerfScan = useCallback(async () => {
    if (!workspacePath) return
    setPerfLoading(true)
    try {
      const res = await fetch(`${API}/profiler/workspace`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ workspacePath, maxFiles: 30 }),
      })
      if (res.ok) {
        const data = await res.json()
        setPerfResults(data.files || [])
      }
    } catch {}
    setPerfLoading(false)
  }, [workspacePath, token])

  useEffect(() => {
    if (showPerf && perfResults.length === 0) fetchPerfScan()
  }, [showPerf])

  // ── Semantic search ────────────────────────────────────────────

  const runSemanticSearch = async () => {
    if (!semanticQuery.trim() || !workspacePath) return
    setSemanticSearching(true)
    try {
      const res = await fetch(`${API}/search/semantic`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ query: semanticQuery, workspacePath, maxResults: 12 }),
      })
      if (res.ok) {
        const data = await res.json()
        setSemanticResults(data.results || [])
      }
    } catch {}
    setSemanticSearching(false)
  }

  // ── Fetch external issues ───────────────────────────────────

  const fetchExtIssues = useCallback(async () => {
    setExtIssuesLoading(true)
    try {
      const res = await fetch(`${API}/integrations/issues?limit=25`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setExtIssues(data.issues || [])
        setExtIssuesProvider(data.provider || '')
      }
    } catch {}
    setExtIssuesLoading(false)
  }, [token])

  useEffect(() => {
    if (showExtIssues) fetchExtIssues()
  }, [showExtIssues, fetchExtIssues])

  // ── Fetch file content ────────────────────────────────────────

  const fetchFileContent = async (relativePath: string) => {
    if (fileContents[relativePath] !== undefined) return
    setEditorLoading(true)
    try {
      const abs = workspacePath + '/' + relativePath
      const res = await fetch(`${API}/files/content?path=${encodeURIComponent(abs)}`, {
        headers: authHeaders(token),
      })
      if (!res.ok) throw new Error('Failed to load file')
      const data = await res.json()
      setFileContents(prev => ({ ...prev, [relativePath]: data.content }))
    } catch {
      setFileContents(prev => ({ ...prev, [relativePath]: '// Failed to load file' }))
    } finally {
      setEditorLoading(false)
    }
  }

  // ── Open / close files ────────────────────────────────────────

  const openFile = (path: string) => {
    if (!openFiles.includes(path)) setOpenFiles(prev => [...prev, path])
    setActiveFile(path)
    fetchFileContent(path)
  }

  const closeFile = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const next = openFiles.filter(f => f !== path)
    setOpenFiles(next)
    if (activeFile === path && next.length > 0) setActiveFile(next[next.length - 1])
    else if (next.length === 0) setActiveFile('')
  }

  // ── Save file ─────────────────────────────────────────────────

  const saveFile = async () => {
    if (!activeFile || !dirty.has(activeFile)) return
    const abs = workspacePath + '/' + activeFile
    try {
      await fetch(`${API}/files/save`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ path: abs, content: fileContents[activeFile] || '' }),
      })
      setDirty(prev => { const n = new Set(prev); n.delete(activeFile); return n })
    } catch { /* silently fail for now */ }
  }

  // Keyboard shortcut: Cmd/Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        saveFile()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })

  // ── Agent Presence WebSocket ───────────────────────────────────

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${window.location.host}/api/v1/ws/presence`
    let ws: WebSocket | null = null
    let pingInterval: ReturnType<typeof setInterval>

    try {
      ws = new WebSocket(wsUrl)
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'agents_list') {
            setAgentPresence(data.agents || [])
          } else if (data.type === 'agent_active') {
            setAgentPresence(prev => {
              const filtered = prev.filter(a => a.agent !== data.agent)
              return [...filtered, { agent: data.agent, file: data.file, line: data.line, action: data.action }]
            })
          } else if (data.type === 'agent_idle') {
            setAgentPresence(prev => prev.filter(a => a.agent !== data.agent))
          }
        } catch {}
      }
      ws.onopen = () => {
        pingInterval = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
        }, 25000)
      }
      ws.onerror = () => {}
      ws.onclose = () => clearInterval(pingInterval)
    } catch {}

    return () => {
      clearInterval(pingInterval)
      ws?.close()
    }
  }, [])

  // Decorate Monaco editor with agent presence highlights
  useEffect(() => {
    if (!editorRef.current || !monacoRef.current || !activeFile) return
    const editor = editorRef.current
    const monaco = monacoRef.current

    const activeAgents = agentPresence.filter(a => activeFile.endsWith(a.file) || a.file.endsWith(activeFile))

    if (activeAgents.length === 0) {
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [])
      return
    }

    const decorations = activeAgents.map(a => ({
      range: new monaco.Range(Math.max(1, a.line), 1, Math.max(1, a.line), 1),
      options: {
        isWholeLine: true,
        className: 'agent-active-line',
        glyphMarginClassName: 'agent-active-glyph',
        glyphMarginHoverMessage: { value: `🤖 **${a.agent}** is ${a.action} here` },
        overviewRuler: { color: '#10b981', position: 1 },
      },
    }))

    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations)
  }, [agentPresence, activeFile])

  // ── Folder toggle ─────────────────────────────────────────────

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const n = new Set(prev)
      n.has(path) ? n.delete(path) : n.add(path)
      return n
    })
  }

  // ── Terminal ──────────────────────────────────────────────────

  const runTerminalCommand = async () => {
    const cmd = terminalInput.trim()
    if (!cmd || terminalRunning) return
    setTerminalOutput(prev => [...prev, `$ ${cmd}`])
    setTerminalInput('')

    if (cmd === 'clear') {
      setTerminalOutput([])
      return
    }

    setTerminalRunning(true)
    try {
      const res = await fetch(`${API}/terminal/exec`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ command: cmd, cwd: workspacePath }),
      })
      const data = await res.json()
      const lines: string[] = []
      if (data.stdout) lines.push(...data.stdout.split('\n'))
      if (data.stderr) lines.push(...data.stderr.split('\n'))
      if (lines.length === 0) lines.push('(no output)')
      setTerminalOutput(prev => [...prev, ...lines])
    } catch {
      setTerminalOutput(prev => [...prev, 'Error: could not reach backend'])
    } finally {
      setTerminalRunning(false)
    }
  }

  useEffect(() => {
    terminalRef.current?.scrollTo(0, terminalRef.current.scrollHeight)
  }, [terminalOutput])

  // ── AI Chat ───────────────────────────────────────────────────

  const sendChatMessage = async () => {
    const msg = chatInput.trim()
    if (!msg || isGenerating) return

    setChatMessages(prev => [...prev, { role: 'user', content: msg }])
    setChatInput('')
    setIsGenerating(true)

    try {
      const res = await fetch(`${API}/chat/query`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          query: msg,
          workspacePath,
          maxContextTokens: 4000,
          maxHops: 2,
          maxFiles: 10,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Chat request failed')
      }
      const data = await res.json()
      const answer = data.answer || 'No response from the AI.'
      const filesUsed = data.context?.filesUsed || []
      const contextNote = filesUsed.length > 0
        ? `\n\n_Context: ${filesUsed.length} files analyzed from Knowledge Graph_`
        : ''
      setChatMessages(prev => [...prev, { role: 'assistant', content: answer + contextNote }])
    } catch (e: any) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${e.message}. Make sure the backend is running.`,
      }])
    } finally {
      setIsGenerating(false)
    }
  }

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight)
  }, [chatMessages])

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
  }

  const applyCode = (code: string) => {
    const cur = fileContents[activeFile] || ''
    setFileContents(prev => ({ ...prev, [activeFile]: cur + '\n\n' + code }))
    setDirty(prev => new Set(prev).add(activeFile))
  }

  // ── Monaco mount ──────────────────────────────────────────────

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco
    editor.focus()

    // Go-to-Definition via Ctrl/Cmd+Click or F12
    editor.addAction({
      id: 'code4u-goto-definition',
      label: 'Go to Definition',
      keybindings: [monaco.KeyCode.F12],
      run: async (ed: any) => {
        const position = ed.getPosition()
        if (!position || !activeFile) return
        const model = ed.getModel()
        if (!model) return
        const word = model.getWordAtPosition(position)
        if (!word) return

        try {
          const res = await fetch(
            `${API}/symbols/goto?workspace=${encodeURIComponent(workspacePath)}&symbol=${encodeURIComponent(word.word)}&fromFile=${encodeURIComponent(activeFile)}`,
            { headers: authHeaders(token) },
          )
          if (res.ok) {
            const data = await res.json()
            if (data.definitions && data.definitions.length > 0) {
              const def = data.definitions[0]
              openFile(def.filePath)
              setTimeout(() => {
                const currentEditor = editorRef.current
                if (currentEditor) {
                  currentEditor.revealLineInCenter(def.startLine)
                  currentEditor.setPosition({ lineNumber: def.startLine, column: 1 })
                }
              }, 300)
            }
          }
        } catch {}
      },
    })
  }

  // ── Render file tree ──────────────────────────────────────────

  const renderFileTree = (nodes: FileNode[]) => {
    return nodes.map(node => {
      const isExpanded = expandedFolders.has(node.path)

      if (node.type === 'folder') {
        return (
          <div key={node.path}>
            <button
              onClick={() => toggleFolder(node.path)}
              className="w-full flex items-center gap-1 px-2 py-1 hover:bg-white/5 rounded text-sm text-white/70 hover:text-white"
            >
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              <FolderOpen className="w-4 h-4 text-yellow-400" />
              <span className="truncate">{node.name}</span>
            </button>
            {isExpanded && node.children && (
              <div className="ml-4">{renderFileTree(node.children)}</div>
            )}
          </div>
        )
      }

      const hasAgent = agentPresence.some(a => a.file.endsWith(node.path) || node.path.endsWith(a.file))
      return (
        <button
          key={node.path}
          onClick={() => openFile(node.path)}
          className={`w-full flex items-center gap-1 px-2 py-1 rounded text-sm ${
            activeFile === node.path ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
          }`}
        >
          <File className="w-4 h-4 text-blue-400 ml-5" />
          <span className="truncate flex-1">{node.name}</span>
          {hasAgent && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-presence-pulse shrink-0" title="Agent active" />
          )}
        </button>
      )
    })
  }

  // ── Workspace Picker ──────────────────────────────────────────

  if (showWorkspacePicker) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0d1117] text-white">
        <div className="w-full max-w-lg p-8">
          <div className="flex items-center gap-3 mb-6">
            <FolderInput className="w-8 h-8 text-emerald-400" />
            <div>
              <h1 className="text-xl font-bold">Open Workspace</h1>
              <p className="text-sm text-white/50">Enter the absolute path to your project folder</p>
            </div>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={workspaceInput}
              onChange={(e) => setWorkspaceInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && workspaceInput.trim() && setWorkspace(workspaceInput)}
              placeholder="/Users/you/projects/my-app"
              className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm focus:outline-none focus:border-emerald-500/50 font-mono"
              autoFocus
            />
            <button
              onClick={() => workspaceInput.trim() && setWorkspace(workspaceInput)}
              className="px-6 py-3 bg-emerald-500 hover:bg-emerald-600 rounded-xl font-medium transition-colors"
            >
              Open
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Main IDE Layout ───────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col bg-[#0d1117] text-white overflow-hidden">
      {/* Header */}
      <header className="h-12 bg-[#161b22] border-b border-white/10 flex items-center justify-between px-4 flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="code4u.ai" className="w-7 h-7 rounded-lg" />
            <span className="font-bold">code4u.ai</span>
            <span className="text-white/40 text-sm">IDE</span>
          </div>
          <button
            onClick={() => setShowWorkspacePicker(true)}
            className="flex items-center gap-1 text-sm text-white/50 hover:text-white transition-colors"
          >
            <FolderGit2 className="w-4 h-4" />
            <span className="truncate max-w-[200px] font-mono text-xs">{workspacePath.split('/').pop()}</span>
            <GitBranch className="w-4 h-4 ml-2" />
            <span>main</span>
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={saveFile}
            disabled={!activeFile || !dirty.has(activeFile)}
            className="flex items-center gap-2 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition-colors disabled:opacity-30"
          >
            <Save className="w-4 h-4" />
            Save
          </button>
          <button
            onClick={runTests}
            disabled={testRunning || !workspacePath}
            className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {testRunning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <TestTube2 className="w-4 h-4" />
            )}
            {testRunning ? 'Running...' : 'Run Tests'}
          </button>

          {/* Agent Presence Indicator */}
          {agentPresence.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg animate-fade-in">
              <Zap className="w-3.5 h-3.5 text-emerald-400 animate-presence-pulse" />
              <span className="text-xs text-emerald-400">
                {agentPresence.length} agent{agentPresence.length > 1 ? 's' : ''} active
              </span>
              {agentPresence.slice(0, 2).map((a, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 bg-emerald-500/20 rounded text-emerald-300">
                  {a.agent}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={() => window.location.href = '/'}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            title="Back to Dashboard"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar — File Explorer */}
        {showSidebar && (
          <div className="w-60 bg-[#0d1117] border-r border-white/10 flex flex-col flex-shrink-0">
            <div className="p-3 border-b border-white/10 flex items-center justify-between">
              <span className="text-xs font-semibold text-white/50 uppercase">Explorer</span>
              <div className="flex gap-1">
                <button onClick={fetchTree} className="p-1 hover:bg-white/10 rounded" title="Refresh">
                  <RefreshCw className={`w-4 h-4 text-white/50 ${treeLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {treeLoading && files.length === 0 && (
                <div className="flex items-center gap-2 p-2 text-sm text-white/50">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading...
                </div>
              )}
              {treeError && (
                <div className="flex items-center gap-2 p-2 text-sm text-red-400">
                  <AlertCircle className="w-4 h-4" /> {treeError}
                </div>
              )}
              {renderFileTree(files)}
            </div>
          </div>
        )}

        {/* Editor + Terminal */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Tabs */}
          <div className="h-9 bg-[#161b22] flex items-center gap-0.5 px-2 overflow-x-auto flex-shrink-0">
            <button onClick={() => setShowSidebar(!showSidebar)} className="p-1.5 hover:bg-white/10 rounded mr-2">
              {showSidebar ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
            </button>
            {openFiles.map(file => (
              <div
                key={file}
                onClick={() => { setActiveFile(file); fetchFileContent(file) }}
                className={`flex items-center gap-2 px-3 py-1 rounded-t cursor-pointer text-sm whitespace-nowrap ${
                  activeFile === file ? 'bg-[#0d1117] text-white' : 'text-white/50 hover:text-white'
                }`}
              >
                <File className="w-3 h-3 flex-shrink-0" />
                <span>{file.split('/').pop()}</span>
                {dirty.has(file) && <span className="w-2 h-2 bg-amber-400 rounded-full" />}
                <button onClick={(e) => closeFile(file, e)} className="ml-1 p-0.5 hover:bg-white/20 rounded">
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>

          {/* Monaco Editor */}
          <div className="flex-1 overflow-hidden relative">
            {activeFile ? (
              <>
                {editorLoading && !(fileContents[activeFile] !== undefined) && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117] z-10">
                    <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
                  </div>
                )}
                <Editor
                  height="100%"
                  language={langFromPath(activeFile)}
                  value={fileContents[activeFile] ?? ''}
                  theme="vs-dark"
                  onChange={(value) => {
                    setFileContents(prev => ({ ...prev, [activeFile]: value || '' }))
                    setDirty(prev => new Set(prev).add(activeFile))
                  }}
                  onMount={handleEditorMount}
                  options={{
                    fontSize: 14,
                    fontFamily: "'Fira Code', 'JetBrains Mono', Menlo, Monaco, monospace",
                    minimap: { enabled: true },
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    wordWrap: 'on',
                    tabSize: 2,
                    renderWhitespace: 'selection',
                    bracketPairColorization: { enabled: true },
                    padding: { top: 12 },
                    glyphMargin: true,
                  }}
                />
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-white/30 text-sm">
                <div className="text-center">
                  <Sparkles className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p>Select a file from the explorer to start editing</p>
                </div>
              </div>
            )}
          </div>

          {/* Terminal */}
          {showTerminal && (
            <div className="h-48 bg-[#0d1117] border-t border-white/10 flex flex-col flex-shrink-0">
              <div className="h-8 bg-[#161b22] flex items-center justify-between px-3 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <TerminalIcon className="w-4 h-4 text-white/50" />
                  <span className="text-xs text-white/50">Terminal</span>
                  {terminalRunning && <Loader2 className="w-3 h-3 animate-spin text-emerald-400" />}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => setTerminalOutput([])} className="p-1 hover:bg-white/10 rounded" title="Clear">
                    <RefreshCw className="w-3 h-3 text-white/50" />
                  </button>
                  <button onClick={() => setShowTerminal(false)} className="p-1 hover:bg-white/10 rounded">
                    <X className="w-3 h-3 text-white/50" />
                  </button>
                </div>
              </div>
              <div ref={terminalRef} className="flex-1 overflow-y-auto p-3 font-mono text-sm">
                {terminalOutput.map((line, i) => (
                  <div key={i} className={line.startsWith('$') ? 'text-emerald-400' : 'text-white/70'}>
                    {line || '\u00A0'}
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 px-3 pb-2">
                <span className="text-emerald-400 font-mono text-sm">$</span>
                <input
                  type="text"
                  value={terminalInput}
                  onChange={(e) => setTerminalInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && runTerminalCommand()}
                  placeholder="Enter command..."
                  className="flex-1 bg-transparent text-white font-mono text-sm focus:outline-none"
                  disabled={terminalRunning}
                />
              </div>
            </div>
          )}
        </div>

        {/* AI Chat Panel */}
        {showChat && (
          <div className="w-80 bg-[#0d1117] border-l border-white/10 flex flex-col flex-shrink-0">
            <div className="h-12 bg-[#161b22] flex items-center justify-between px-4 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-400" />
                <span className="font-medium text-sm">AI Assistant</span>
              </div>
              <button onClick={() => setShowChat(false)} className="p-1 hover:bg-white/10 rounded">
                <X className="w-4 h-4 text-white/50" />
              </button>
            </div>

            <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  role={msg.role}
                  content={msg.content}
                  code={msg.code}
                  onCopy={copyCode}
                  onApply={applyCode}
                />
              ))}
              {isGenerating && (
                <div className="flex gap-3 items-center">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    <span className="text-xs text-white/30 ml-1">Thinking...</span>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-white/10">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendChatMessage()}
                  placeholder="Ask about your code..."
                  className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-emerald-500/50"
                  disabled={isGenerating}
                />
                <button onClick={sendChatMessage} disabled={isGenerating} className="p-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg disabled:opacity-50 transition-colors">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Performance Panel */}
        {showPerf && (
          <div className="w-80 bg-[#0d1117] border-l border-white/10 flex flex-col flex-shrink-0">
            <div className="h-12 bg-[#161b22] flex items-center justify-between px-4 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-orange-400" />
                <span className="font-medium text-sm">Performance</span>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={fetchPerfScan} className="p-1 hover:bg-white/10 rounded" title="Rescan">
                  <RefreshCw className={`w-3 h-3 text-white/50 ${perfLoading ? 'animate-spin' : ''}`} />
                </button>
                <button onClick={() => setShowPerf(false)} className="p-1 hover:bg-white/10 rounded">
                  <X className="w-4 h-4 text-white/50" />
                </button>
              </div>
            </div>

            {/* Semantic Search */}
            <div className="px-3 py-2 border-b border-white/10">
              <div className="flex gap-1.5">
                <input
                  type="text"
                  value={semanticQuery}
                  onChange={e => setSemanticQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && runSemanticSearch()}
                  placeholder="Search by concept..."
                  className="flex-1 px-2.5 py-1.5 bg-black/30 border border-white/10 rounded text-xs focus:outline-none focus:border-orange-500/50"
                />
                <button
                  onClick={runSemanticSearch}
                  disabled={semanticSearching}
                  className="px-2 py-1.5 bg-orange-500/20 text-orange-400 rounded text-xs hover:bg-orange-500/30 disabled:opacity-50"
                >
                  {semanticSearching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                </button>
              </div>
            </div>

            {/* Semantic results */}
            {semanticResults.length > 0 && (
              <div className="border-b border-white/10 max-h-48 overflow-y-auto">
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-white/20">
                  Concept matches
                </div>
                {semanticResults.map((r, i) => (
                  <button
                    key={i}
                    onClick={() => openFile(r.filePath)}
                    className="w-full text-left px-3 py-2 hover:bg-white/5 border-b border-white/5 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-white/70 truncate">{r.filePath}</span>
                      <span className="text-[9px] text-orange-400 font-mono">{Math.round(r.score * 100)}%</span>
                    </div>
                    {r.snippet && (
                      <pre className="text-[9px] text-white/30 mt-1 truncate font-mono">{r.snippet.split('\n')[0]}</pre>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Stats */}
            <div className="px-4 py-3 border-b border-white/10 flex gap-4 text-xs">
              <div className="text-center">
                <p className="text-lg font-bold text-red-400">
                  {perfResults.filter(f => f.smellCount > 0).length}
                </p>
                <p className="text-white/40">Hot Files</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-orange-400">
                  {perfResults.reduce((s, f) => s + f.smellCount, 0)}
                </p>
                <p className="text-white/40">Smells</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-amber-400">
                  {Math.max(...perfResults.map(f => f.maxComplexity), 0)}
                </p>
                <p className="text-white/40">Max CC</p>
              </div>
            </div>

            {/* File list */}
            <div className="flex-1 overflow-y-auto">
              {perfLoading && perfResults.length === 0 && (
                <div className="flex items-center gap-2 p-4 text-sm text-white/50">
                  <Loader2 className="w-4 h-4 animate-spin" /> Scanning workspace...
                </div>
              )}

              {!perfLoading && perfResults.length === 0 && (
                <div className="p-6 text-center text-xs text-white/30">
                  <Gauge className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p>No performance issues found.</p>
                </div>
              )}

              {perfResults.map((file, idx) => {
                const ccColor = file.maxComplexity > 15 ? 'text-red-400' :
                  file.maxComplexity > 8 ? 'text-orange-400' : 'text-amber-400'
                return (
                  <div key={idx} className="border-b border-white/5">
                    <button
                      onClick={() => openFile(file.filePath)}
                      className="w-full text-left px-3 py-2.5 hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-white/70 truncate flex-1">{file.filePath}</span>
                        <span className={`text-[9px] font-bold ml-2 ${ccColor}`}>CC:{file.maxComplexity}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[9px] text-white/30">
                        <span>{file.lines} lines</span>
                        {file.smellCount > 0 && (
                          <span className="text-orange-400">{file.smellCount} smell{file.smellCount > 1 ? 's' : ''}</span>
                        )}
                      </div>
                    </button>
                    {file.smells && file.smells.length > 0 && (
                      <div className="px-3 pb-2 space-y-1">
                        {file.smells.slice(0, 3).map((s, si) => (
                          <div key={si} className="text-[9px] text-white/30 flex items-start gap-1.5 pl-2">
                            <Flame className={`w-2.5 h-2.5 shrink-0 mt-0.5 ${
                              s.severity === 'critical' ? 'text-red-400' : s.severity === 'warning' ? 'text-orange-400' : 'text-amber-400'
                            }`} />
                            <span>{s.description.slice(0, 80)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* External Issues Panel (Jira/Linear/GitHub) */}
        {showExtIssues && (
          <div className="w-80 bg-[#0d1117] border-l border-white/10 flex flex-col flex-shrink-0">
            <div className="h-12 bg-[#161b22] flex items-center justify-between px-4 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Ticket className="w-4 h-4 text-blue-400" />
                <span className="font-medium text-sm">Tracker</span>
                {extIssuesProvider && extIssuesProvider !== 'demo' && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded capitalize">
                    {extIssuesProvider}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button onClick={fetchExtIssues} className="p-1 hover:bg-white/10 rounded" title="Refresh">
                  <RefreshCw className={`w-3 h-3 text-white/50 ${extIssuesLoading ? 'animate-spin' : ''}`} />
                </button>
                <button onClick={() => setShowExtIssues(false)} className="p-1 hover:bg-white/10 rounded">
                  <X className="w-4 h-4 text-white/50" />
                </button>
              </div>
            </div>

            {/* Stats */}
            <div className="px-4 py-3 border-b border-white/10 flex gap-4 text-xs">
              <div className="text-center">
                <p className="text-lg font-bold text-red-400">
                  {extIssues.filter(i => i.priority === 'high' || i.type === 'bug').length}
                </p>
                <p className="text-white/40">Bugs</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-blue-400">
                  {extIssues.filter(i => i.type === 'feature' || i.type === 'enhancement').length}
                </p>
                <p className="text-white/40">Features</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-white/60">
                  {extIssues.length}
                </p>
                <p className="text-white/40">Total</p>
              </div>
            </div>

            {/* Issues list */}
            <div className="flex-1 overflow-y-auto">
              {extIssuesLoading && extIssues.length === 0 && (
                <div className="flex items-center gap-2 p-4 text-sm text-white/50">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading issues...
                </div>
              )}

              {!extIssuesLoading && extIssues.length === 0 && (
                <div className="p-6 text-center text-xs text-white/30">
                  <Ticket className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p>No issues found.</p>
                  <p className="mt-1">Configure a tracker in Integrations.</p>
                </div>
              )}

              {extIssues.map((issue) => {
                const prioColor = issue.priority === 'high' ? 'text-red-400' :
                  issue.priority === 'medium' ? 'text-amber-400' : 'text-blue-400'
                const typeIcon = issue.type === 'bug' ? '🐛' :
                  issue.type === 'feature' || issue.type === 'enhancement' ? '✨' : '📋'

                return (
                  <div
                    key={`${issue.provider}-${issue.id}`}
                    className="px-3 py-2.5 hover:bg-white/5 transition-colors border-b border-white/5 cursor-default"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-sm mt-0.5">{typeIcon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-[10px] font-mono text-white/30">{issue.key}</span>
                          <span className={`text-[9px] font-bold uppercase ${prioColor}`}>
                            {issue.priority}
                          </span>
                        </div>
                        <p className="text-[11px] text-white/70 leading-snug">{issue.title}</p>
                        {issue.labels.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {issue.labels.slice(0, 3).map(l => (
                              <span key={l} className="text-[9px] px-1 py-0 bg-white/5 text-white/30 rounded flex items-center gap-0.5">
                                <Tag className="w-2 h-2" />{l}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          {issue.assignee && (
                            <span className="text-[9px] text-white/20">{issue.assignee}</span>
                          )}
                          {issue.url && (
                            <a
                              href={issue.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[9px] text-blue-400/50 hover:text-blue-400 flex items-center gap-0.5"
                              onClick={e => e.stopPropagation()}
                            >
                              <ExternalLink className="w-2.5 h-2.5" /> Open
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}

              {extIssuesProvider === 'demo' && extIssues.length > 0 && (
                <div className="p-3 text-center text-[10px] text-white/20 border-t border-white/5">
                  Demo data. Connect Jira or GitHub Issues for real issues.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Issues Panel (Architectural Debt) */}
        {showIssues && (
          <div className="w-80 bg-[#0d1117] border-l border-white/10 flex flex-col flex-shrink-0">
            <div className="h-12 bg-[#161b22] flex items-center justify-between px-4 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Bug className="w-4 h-4 text-amber-400" />
                <span className="font-medium text-sm">Issues</span>
                {issues.length > 0 && (
                  <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] font-bold rounded">
                    {issues.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button onClick={fetchIssues} className="p-1 hover:bg-white/10 rounded" title="Rescan">
                  <RefreshCw className={`w-3 h-3 text-white/50 ${issuesLoading ? 'animate-spin' : ''}`} />
                </button>
                <button onClick={() => setShowIssues(false)} className="p-1 hover:bg-white/10 rounded">
                  <X className="w-4 h-4 text-white/50" />
                </button>
              </div>
            </div>

            {/* Summary bar */}
            <div className="px-4 py-3 border-b border-white/10 flex gap-4 text-xs">
              <div className="text-center">
                <p className="text-lg font-bold text-red-400">
                  {issues.filter(i => i.severity === 'error').length}
                </p>
                <p className="text-white/40">Errors</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-amber-400">
                  {issues.filter(i => i.severity === 'warning').length}
                </p>
                <p className="text-white/40">Warnings</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-blue-400">
                  {issues.filter(i => i.severity === 'info').length}
                </p>
                <p className="text-white/40">Info</p>
              </div>
            </div>

            {/* Test result banner */}
            {testResult && (
              <div className={`mx-3 mt-3 rounded-lg p-2.5 flex items-center gap-2 text-xs ${
                testResult.status === 'pass'
                  ? 'bg-emerald-500/10 border border-emerald-500/20'
                  : 'bg-red-500/10 border border-red-500/20'
              }`}>
                {testResult.status === 'pass' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                )}
                <div>
                  <p className={`font-medium ${testResult.status === 'pass' ? 'text-emerald-400' : 'text-red-400'}`}>
                    Tests {testResult.status === 'pass' ? 'passing' : 'failing'}
                  </p>
                  <p className="text-white/40">
                    {testResult.framework} · {testResult.durationMs}ms
                    {testResult.failedTests.length > 0 && ` · ${testResult.failedTests.length} failed`}
                  </p>
                </div>
              </div>
            )}

            {/* Issues list */}
            <div className="flex-1 overflow-y-auto">
              {issuesLoading && issues.length === 0 && (
                <div className="flex items-center gap-2 p-4 text-sm text-white/50">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Scanning files ({issuesScanned})...</span>
                </div>
              )}

              {!issuesLoading && issues.length === 0 && (
                <div className="p-6 text-center text-xs text-white/30">
                  <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p>No issues found.</p>
                  <p className="mt-1">Your code looks clean!</p>
                </div>
              )}

              {issues.map((issue, i) => (
                <button
                  key={`${issue.filePath}-${issue.line}-${i}`}
                  onClick={() => {
                    const relPath = issue.filePath.startsWith(workspacePath)
                      ? issue.filePath.slice(workspacePath.length + 1)
                      : issue.filePath
                    openFile(relPath)
                  }}
                  className="w-full text-left px-3 py-2.5 hover:bg-white/5 transition-colors border-b border-white/5"
                >
                  <div className="flex items-start gap-2">
                    {issue.severity === 'error' ? (
                      <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
                    ) : issue.severity === 'warning' ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                    ) : (
                      <Info className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className={`text-[9px] font-bold uppercase tracking-wider ${
                          issue.severity === 'error' ? 'text-red-400' :
                          issue.severity === 'warning' ? 'text-amber-400' : 'text-blue-400'
                        }`}>
                          {issue.category}
                        </span>
                        {issue.line > 0 && (
                          <span className="text-[9px] text-white/30 font-mono">L{issue.line}</span>
                        )}
                      </div>
                      <p className="text-[11px] text-white/60 leading-snug">{issue.message}</p>
                      {issue.suggestion && (
                        <p className="text-[10px] text-violet-400/60 mt-0.5 italic">{issue.suggestion}</p>
                      )}
                      <p className="text-[9px] text-white/20 font-mono mt-0.5 truncate">
                        {issue.filePath.split('/').slice(-2).join('/')}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Knowledge Graph Panel */}
        {showGraph && (
          <div className="w-72 bg-[#0d1117] border-l border-white/10 flex flex-col flex-shrink-0">
            <div className="h-12 bg-[#161b22] flex items-center justify-between px-4 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-cyan-400" />
                <span className="font-medium text-sm">Knowledge Graph</span>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={fetchGraphHotSpots} className="p-1 hover:bg-white/10 rounded">
                  <RefreshCw className={`w-3 h-3 text-white/50 ${graphLoading ? 'animate-spin' : ''}`} />
                </button>
                <button onClick={() => setShowGraph(false)} className="p-1 hover:bg-white/10 rounded">
                  <X className="w-4 h-4 text-white/50" />
                </button>
              </div>
            </div>

            {/* Stats */}
            <div className="px-4 py-3 border-b border-white/10 flex gap-4 text-xs">
              <div className="text-center">
                <p className="text-lg font-bold text-cyan-400">{graphStats.totalFiles}</p>
                <p className="text-white/40">Files</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-purple-400">{graphStats.totalSymbols}</p>
                <p className="text-white/40">Symbols</p>
              </div>
            </div>

            {/* Hot Spots list */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-3 py-2">
                <h3 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1">
                  <Flame className="w-3 h-3 text-amber-400" /> Hot Spots
                </h3>
              </div>
              {graphLoading && hotSpots.length === 0 && (
                <div className="flex items-center gap-2 p-4 text-sm text-white/50">
                  <Loader2 className="w-4 h-4 animate-spin" /> Indexing...
                </div>
              )}
              {hotSpots.map((sym, i) => (
                <button
                  key={`${sym.file}-${sym.name}-${i}`}
                  onClick={() => {
                    const relPath = sym.file.startsWith(workspacePath)
                      ? sym.file.slice(workspacePath.length + 1)
                      : sym.file
                    openFile(relPath)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-white/5"
                >
                  <div className="flex items-center gap-2">
                    <span className={`px-1 py-0.5 rounded text-[9px] font-bold uppercase ${
                      sym.kind === 'class' ? 'bg-purple-500/20 text-purple-400' :
                      sym.kind === 'function' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-white/10 text-white/50'
                    }`}>
                      {sym.kind.slice(0, 3)}
                    </span>
                    <span className="text-sm text-white/80 font-mono truncate">{sym.name}</span>
                  </div>
                  <p className="text-[10px] text-white/30 truncate mt-0.5 ml-7">
                    {sym.file.split('/').slice(-2).join('/')}:{sym.startLine}
                  </p>
                  {sym.docstring && (
                    <p className="text-[10px] text-white/20 truncate mt-0.5 ml-7 italic">{sym.docstring}</p>
                  )}
                </button>
              ))}
              {!graphLoading && hotSpots.length === 0 && (
                <p className="p-4 text-xs text-white/30 text-center">No symbols indexed yet. Open a Python workspace to see results.</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Status Bar */}
      <footer className="h-6 bg-[#161b22] border-t border-white/10 flex items-center justify-between px-4 text-xs text-white/50 flex-shrink-0">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1"><GitBranch className="w-3 h-3" /> main</span>
          {activeFile && <span>{langFromPath(activeFile)}</span>}
          {dirty.size > 0 && <span className="text-amber-400">{dirty.size} unsaved</span>}
        </div>
        <div className="flex items-center gap-4">
          <button onClick={() => setShowTerminal(!showTerminal)} className="hover:text-white">Terminal</button>
          <button onClick={() => setShowChat(!showChat)} className="hover:text-white flex items-center gap-1">
            <MessageSquare className="w-3 h-3" /> AI Chat
          </button>
          <button
            onClick={() => { setShowIssues(!showIssues); if (!showIssues) { setShowGraph(false); setShowExtIssues(false); setShowPerf(false) } }}
            className={`hover:text-white flex items-center gap-1 ${showIssues ? 'text-amber-400' : ''}`}
          >
            <Bug className="w-3 h-3" /> Issues
            {issues.length > 0 && (
              <span className="px-1 py-0 bg-amber-500/20 text-amber-400 text-[9px] font-bold rounded">
                {issues.length}
              </span>
            )}
          </button>
          <button
            onClick={() => { setShowPerf(!showPerf); if (!showPerf) { setShowGraph(false); setShowIssues(false); setShowExtIssues(false) } }}
            className={`hover:text-white flex items-center gap-1 ${showPerf ? 'text-orange-400' : ''}`}
          >
            <Gauge className="w-3 h-3" /> Perf
            {perfResults.length > 0 && (
              <span className="px-1 py-0 bg-orange-500/20 text-orange-400 text-[9px] font-bold rounded">
                {perfResults.reduce((s, f) => s + f.smellCount, 0)}
              </span>
            )}
          </button>
          <button
            onClick={() => { setShowExtIssues(!showExtIssues); if (!showExtIssues) { setShowGraph(false); setShowIssues(false); setShowPerf(false) } }}
            className={`hover:text-white flex items-center gap-1 ${showExtIssues ? 'text-blue-400' : ''}`}
          >
            <Ticket className="w-3 h-3" /> Tracker
            {extIssues.length > 0 && (
              <span className="px-1 py-0 bg-blue-500/20 text-blue-400 text-[9px] font-bold rounded">
                {extIssues.length}
              </span>
            )}
          </button>
          <button onClick={() => { setShowGraph(!showGraph); if (!showGraph) { setShowIssues(false); setShowExtIssues(false); setShowPerf(false) } }} className="hover:text-white flex items-center gap-1">
            <Network className="w-3 h-3" /> Graph
          </button>
          <span className="font-mono">{workspacePath.split('/').pop()}</span>
        </div>
      </footer>
    </div>
  )
}
