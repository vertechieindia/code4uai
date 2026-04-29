import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Command } from 'cmdk'
import {
  Search,
  File,
  Sparkles,
  GitBranch,
  FolderOpen,
  Settings,
  RefreshCw,
  ArrowRight,
  Hash,
  Zap,
  TestTube2,
  Bug,
  LayoutDashboard,
  Bot,
  Puzzle,
  BookOpen,
  Code2,
  Shield,
} from 'lucide-react'

const API = '/api/v1'

interface SearchResult {
  id: string
  label: string
  description?: string
  icon: React.ReactNode
  action: () => void
  group: string
}

function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { token } = useAuth()
  const navigate = useNavigate()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => !o)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const pageActions: SearchResult[] = [
    { id: 'nav-dashboard', label: 'Go to Dashboard', icon: <LayoutDashboard className="w-4 h-4" />, action: () => navigate('/'), group: 'Navigate' },
    { id: 'nav-projects', label: 'Go to Projects', icon: <FolderOpen className="w-4 h-4" />, action: () => navigate('/projects'), group: 'Navigate' },
    { id: 'nav-agent', label: 'Go to AI Agent', icon: <Bot className="w-4 h-4" />, action: () => navigate('/agent'), group: 'Navigate' },
    { id: 'nav-guardian', label: 'Guardian Mission Control', icon: <Shield className="w-4 h-4" />, action: () => navigate('/guardian'), group: 'Navigate' },
    { id: 'nav-ide', label: 'Open IDE', icon: <Code2 className="w-4 h-4" />, action: () => navigate('/ide'), group: 'Navigate' },
    { id: 'nav-refactor', label: 'Open Refactor Engine', icon: <Zap className="w-4 h-4" />, action: () => navigate('/refactor'), group: 'Navigate' },
    { id: 'nav-integrations', label: 'Integrations', icon: <Puzzle className="w-4 h-4" />, action: () => navigate('/integrations'), group: 'Navigate' },
    { id: 'nav-settings', label: 'Settings', icon: <Settings className="w-4 h-4" />, action: () => navigate('/settings'), group: 'Navigate' },
    { id: 'nav-docs', label: 'Documentation', icon: <BookOpen className="w-4 h-4" />, action: () => navigate('/docs'), group: 'Navigate' },
    { id: 'nav-connect', label: 'Connect Repository', icon: <GitBranch className="w-4 h-4" />, action: () => navigate('/connect-repo'), group: 'Navigate' },
    { id: 'act-refactor', label: 'Start a Refactor', description: 'Trigger the AI refactoring engine', icon: <Sparkles className="w-4 h-4 text-emerald-400" />, action: () => navigate('/refactor'), group: 'Actions' },
    { id: 'act-test', label: 'Run Tests', description: 'Execute test suite in the workspace', icon: <TestTube2 className="w-4 h-4 text-emerald-400" />, action: () => navigate('/ide'), group: 'Actions' },
    { id: 'act-issues', label: 'View Code Issues', description: 'Open the architectural debt panel', icon: <Bug className="w-4 h-4 text-amber-400" />, action: () => navigate('/ide'), group: 'Actions' },
  ]

  const searchBackend = useCallback(async (q: string) => {
    if (!q || q.length < 2) {
      setResults([])
      return
    }

    setIsLoading(true)
    const backendResults: SearchResult[] = []

    const workspace = localStorage.getItem('code4u_workspace') || ''

    try {
      const [filesRes, symbolsRes] = await Promise.allSettled([
        workspace
          ? fetch(`${API}/files/tree?path=${encodeURIComponent(workspace)}`, { headers: authHeaders(token) })
          : Promise.reject('no workspace'),
        workspace
          ? fetch(`${API}/symbols/search?query=${encodeURIComponent(q)}&workspace=${encodeURIComponent(workspace)}`, { headers: authHeaders(token) })
          : Promise.reject('no workspace'),
      ])

      if (filesRes.status === 'fulfilled' && filesRes.value.ok) {
        const data = await filesRes.value.json()
        const flatFiles = flattenTree(data.tree || data.children || [])
        const matching = flatFiles
          .filter(f => f.path.toLowerCase().includes(q.toLowerCase()))
          .slice(0, 8)

        for (const f of matching) {
          backendResults.push({
            id: `file-${f.path}`,
            label: f.name,
            description: f.path,
            icon: <File className="w-4 h-4 text-blue-400" />,
            action: () => {
              navigate('/ide')
              setTimeout(() => {
                window.dispatchEvent(new CustomEvent('code4u:open-file', { detail: f.path }))
              }, 300)
            },
            group: 'Files',
          })
        }
      }

      if (symbolsRes.status === 'fulfilled' && symbolsRes.value.ok) {
        const data = await symbolsRes.value.json()
        const symbols = (data.results || data.symbols || []).slice(0, 6)
        for (const sym of symbols) {
          backendResults.push({
            id: `sym-${sym.name}-${sym.file_path || ''}`,
            label: sym.name,
            description: `${sym.kind || sym.type || 'symbol'} in ${sym.file_path || ''}`,
            icon: <Hash className="w-4 h-4 text-violet-400" />,
            action: () => {
              navigate('/ide')
              setTimeout(() => {
                window.dispatchEvent(new CustomEvent('code4u:open-file', { detail: sym.file_path }))
              }, 300)
            },
            group: 'Symbols',
          })
        }
      }
    } catch {}

    setResults(backendResults)
    setIsLoading(false)
  }, [token, navigate])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => searchBackend(query), 250)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, searchBackend])

  const allItems = query.length >= 2
    ? [...results, ...pageActions.filter(a => a.label.toLowerCase().includes(query.toLowerCase()))]
    : pageActions

  const groups = Array.from(new Set(allItems.map(i => i.group)))

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />

      {/* Dialog */}
      <div className="fixed inset-0 z-[101] flex items-start justify-center pt-[15vh]">
        <Command
          className="w-[560px] max-h-[420px] rounded-2xl border border-white/10 bg-[#0d1117]/95 backdrop-blur-2xl shadow-2xl shadow-black/50 overflow-hidden flex flex-col"
          shouldFilter={false}
        >
          {/* Input */}
          <div className="flex items-center gap-3 px-4 border-b border-white/10">
            <Search className="w-4 h-4 text-white/30 shrink-0" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Search files, symbols, or navigate..."
              className="w-full py-3.5 bg-transparent text-sm text-white placeholder:text-white/30 focus:outline-none"
              autoFocus
            />
            {isLoading && <RefreshCw className="w-3.5 h-3.5 text-white/30 animate-spin shrink-0" />}
            <kbd className="text-[10px] text-white/20 border border-white/10 rounded px-1.5 py-0.5 font-mono shrink-0">ESC</kbd>
          </div>

          {/* Results */}
          <Command.List className="overflow-y-auto flex-1 py-2 px-2">
            <Command.Empty className="py-8 text-center text-sm text-white/30">
              {query.length >= 2 ? 'No results found.' : 'Start typing to search...'}
            </Command.Empty>

            {groups.map(group => {
              const items = allItems.filter(i => i.group === group)
              if (items.length === 0) return null
              return (
                <Command.Group key={group} heading={group}>
                  <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-white/20">
                    {group}
                  </div>
                  {items.map(item => (
                    <Command.Item
                      key={item.id}
                      value={item.id}
                      onSelect={() => { item.action(); setOpen(false); setQuery('') }}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-sm text-white/70 data-[selected=true]:bg-white/10 data-[selected=true]:text-white transition-colors"
                    >
                      <span className="shrink-0 opacity-60">{item.icon}</span>
                      <div className="flex-1 min-w-0">
                        <span className="block truncate">{item.label}</span>
                        {item.description && (
                          <span className="block text-[11px] text-white/30 truncate">{item.description}</span>
                        )}
                      </div>
                      <ArrowRight className="w-3 h-3 text-white/10 shrink-0" />
                    </Command.Item>
                  ))}
                </Command.Group>
              )
            })}
          </Command.List>

          {/* Footer */}
          <div className="border-t border-white/10 px-4 py-2 flex items-center gap-4 text-[10px] text-white/20">
            <span className="flex items-center gap-1"><kbd className="border border-white/10 rounded px-1 font-mono">↑↓</kbd> Navigate</span>
            <span className="flex items-center gap-1"><kbd className="border border-white/10 rounded px-1 font-mono">↵</kbd> Open</span>
            <span className="flex items-center gap-1"><kbd className="border border-white/10 rounded px-1 font-mono">⌘K</kbd> Toggle</span>
          </div>
        </Command>
      </div>
    </>
  )
}

function flattenTree(nodes: any[], prefix = ''): Array<{ name: string; path: string }> {
  const result: Array<{ name: string; path: string }> = []
  for (const node of nodes) {
    const path = prefix ? `${prefix}/${node.name}` : node.name
    if (node.type === 'file') {
      result.push({ name: node.name, path })
    }
    if (node.children) {
      result.push(...flattenTree(node.children, path))
    }
  }
  return result
}
