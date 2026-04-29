import { useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../AuthContext'
import {
  FolderGit2,
  Plus,
  Search,
  Clock,
  Grid,
  List,
  FileCode,
  Trash2,
  RefreshCw,
  Loader2,
  ChevronRight,
  Flame,
  BarChart3,
} from 'lucide-react'

const API = '/api/v1'

interface Project {
  id: string
  name: string
  path: string
  description: string
  repoUrl: string
  status: string
  healthScore: number
  totalFiles: number
  totalSymbols: number
  languages: string[]
  createdAt: number
  lastIndexedAt: number
}

interface HeatmapEntry {
  filePath: string
  lines: number
  functions: number
  maxComplexity: number
  avgComplexity: number
  maxNesting: number
  maintenanceBurden: number
  language: string
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const { token } = useAuth()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const [viewMode, setViewMode] = useState<'grid' | 'list' | 'heatmap'>('grid')
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [reindexing, setReindexing] = useState<Set<string>>(new Set())

  // Heatmap state
  const [heatmapProject, setHeatmapProject] = useState<string>('')
  const [heatmapData, setHeatmapData] = useState<HeatmapEntry[]>([])
  const [heatmapLoading, setHeatmapLoading] = useState(false)

  // Language distribution
  const [langDist, setLangDist] = useState<Record<string, Array<{
    language: string; files: number; lines: number; filePercent: number; linePercent: number
  }>>>({})
  const [, setLangLoading] = useState<Set<string>>(new Set())

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/projects`, { headers })
      if (res.ok) {
        const d = await res.json()
        setProjects(d.projects || [])
      }
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchProjects() }, [token])

  const fetchLangDist = useCallback(async (project: Project) => {
    if (langDist[project.id]) return
    setLangLoading(prev => new Set(prev).add(project.id))
    try {
      const res = await fetch(`${API}/symbols/languages?workspace=${encodeURIComponent(project.path)}`, { headers })
      if (res.ok) {
        const data = await res.json()
        setLangDist(prev => ({ ...prev, [project.id]: data.distribution || [] }))
      }
    } catch {}
    setLangLoading(prev => { const n = new Set(prev); n.delete(project.id); return n })
  }, [token, langDist])

  useEffect(() => {
    if (projects.length > 0 && viewMode === 'grid') {
      projects.slice(0, 6).forEach(p => fetchLangDist(p))
    }
  }, [projects, viewMode])

  const fetchHeatmap = useCallback(async (projectId: string) => {
    setHeatmapLoading(true)
    setHeatmapProject(projectId)
    try {
      const res = await fetch(`${API}/projects/${projectId}/heatmap?max_files=100`, { headers })
      if (res.ok) {
        const data = await res.json()
        setHeatmapData(data.files || [])
      }
    } catch {}
    setHeatmapLoading(false)
  }, [token])

  useEffect(() => {
    if (viewMode === 'heatmap' && projects.length > 0 && !heatmapProject) {
      fetchHeatmap(projects[0].id)
    }
  }, [viewMode, projects, heatmapProject, fetchHeatmap])

  const handleReindex = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setReindexing(prev => new Set(prev).add(id))
    try {
      await fetch(`${API}/projects/${id}/index`, { method: 'POST', headers })
      await fetchProjects()
    } catch {}
    setReindexing(prev => { const n = new Set(prev); n.delete(id); return n })
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this project? This only removes it from the registry, not from disk.')) return
    try {
      await fetch(`${API}/projects/${id}`, { method: 'DELETE', headers })
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch {}
  }

  const openProject = (project: Project) => {
    localStorage.setItem('code4u_workspace', project.path)
    navigate('/ide')
  }

  const filtered = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  function healthColor(score: number) {
    if (score >= 80) return 'text-emerald-400 bg-emerald-500/10'
    if (score >= 50) return 'text-amber-400 bg-amber-500/10'
    return 'text-red-400 bg-red-500/10'
  }

  function healthRing(score: number) {
    if (score >= 80) return 'ring-emerald-500/30'
    if (score >= 50) return 'ring-amber-500/30'
    return 'ring-red-500/30'
  }

  function timeSince(ts: number) {
    const diff = Date.now() / 1000 - ts
    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  }

  const langColors: Record<string, string> = {
    Python: '#3572A5', TypeScript: '#3178C6', JavaScript: '#F1E05A',
    Go: '#00ADD8', Java: '#B07219', Rust: '#DEA584', Ruby: '#CC342D',
    'C++': '#F34B7D', C: '#555555', 'C#': '#178600',
    CSS: '#563D7C', SCSS: '#C6538C', HTML: '#E34C26',
    Kotlin: '#A97BFF', Swift: '#F05138', PHP: '#4F5D95',
  }

  function burdenColor(burden: number): string {
    if (burden >= 70) return 'bg-red-500'
    if (burden >= 50) return 'bg-orange-500'
    if (burden >= 30) return 'bg-amber-500'
    if (burden >= 15) return 'bg-yellow-500'
    return 'bg-emerald-500'
  }

  function burdenBg(burden: number): string {
    if (burden >= 70) return 'bg-red-500/20 border-red-500/30'
    if (burden >= 50) return 'bg-orange-500/15 border-orange-500/25'
    if (burden >= 30) return 'bg-amber-500/10 border-amber-500/20'
    if (burden >= 15) return 'bg-yellow-500/10 border-yellow-500/15'
    return 'bg-emerald-500/5 border-emerald-500/10'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-white/50">Manage your indexed workspaces and AI agents</p>
        </div>
        <button
          onClick={() => navigate('/new-project')}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
        >
          <Plus className="w-4 h-4" /> New Project
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects..."
              className="w-80 pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-emerald-500/50"
            />
          </div>
          <span className="text-sm text-white/40">{filtered.length} project{filtered.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
          <button onClick={() => setViewMode('grid')} className={`p-2 rounded ${viewMode === 'grid' ? 'bg-white/10' : 'hover:bg-white/5'}`} title="Grid">
            <Grid className="w-4 h-4" />
          </button>
          <button onClick={() => setViewMode('list')} className={`p-2 rounded ${viewMode === 'list' ? 'bg-white/10' : 'hover:bg-white/5'}`} title="List">
            <List className="w-4 h-4" />
          </button>
          <button onClick={() => setViewMode('heatmap')} className={`p-2 rounded ${viewMode === 'heatmap' ? 'bg-orange-500/20 text-orange-400' : 'hover:bg-white/5'}`} title="Complexity Heatmap">
            <BarChart3 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading projects...
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="text-center py-16">
          <FolderGit2 className="w-12 h-12 mx-auto mb-4 text-white/20" />
          <h3 className="text-lg font-semibold mb-2">
            {searchQuery ? 'No matching projects' : 'No projects yet'}
          </h3>
          <p className="text-white/50 mb-6">
            {searchQuery ? 'Try a different search term' : 'Create your first project to start using the Knowledge Graph'}
          </p>
          {!searchQuery && (
            <button onClick={() => navigate('/new-project')} className="px-6 py-3 bg-emerald-500 rounded-lg font-medium hover:bg-emerald-600 transition-colors">
              Create Project
            </button>
          )}
        </div>
      )}

      {/* ── Heatmap View ──────────────────────────────────────────── */}
      {!loading && viewMode === 'heatmap' && filtered.length > 0 && (
        <div className="space-y-4">
          {/* Project selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-white/50">Heatmap for:</span>
            <select
              value={heatmapProject}
              onChange={(e) => fetchHeatmap(e.target.value)}
              className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-orange-500/50"
            >
              {filtered.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {heatmapLoading && <Loader2 className="w-4 h-4 animate-spin text-orange-400" />}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-white/40">
            <span>Maintenance burden:</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" /> Low</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-500" /> Moderate</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500" /> Elevated</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500" /> High</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" /> Critical</span>
            <span className="ml-auto">Box size = lines of code</span>
          </div>

          {/* Treemap */}
          {heatmapData.length > 0 && (
            <div className="grid gap-1.5" style={{
              gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
            }}>
              {heatmapData.slice(0, 60).map((entry, i) => {
                const sizeClass = entry.lines > 500 ? 'col-span-3 row-span-2' :
                  entry.lines > 200 ? 'col-span-2 row-span-2' :
                  entry.lines > 100 ? 'col-span-2' : ''
                return (
                  <div
                    key={i}
                    className={`${sizeClass} rounded-lg border p-2 cursor-pointer transition-all hover:scale-[1.02] hover:shadow-lg ${burdenBg(entry.maintenanceBurden)}`}
                    onClick={() => {
                      const proj = projects.find(p => p.id === heatmapProject)
                      if (proj) {
                        localStorage.setItem('code4u_workspace', proj.path)
                        navigate('/ide')
                      }
                    }}
                    title={`${entry.filePath}\nLines: ${entry.lines}\nComplexity: ${entry.maxComplexity}\nBurden: ${entry.maintenanceBurden}%`}
                  >
                    <div className="flex items-center gap-1 mb-1">
                      <div className={`w-2 h-2 rounded-full ${burdenColor(entry.maintenanceBurden)}`} />
                      <span className="text-[10px] font-medium truncate text-white/70">
                        {entry.filePath.split('/').pop()}
                      </span>
                    </div>
                    <div className="text-[9px] text-white/30 space-y-0.5">
                      <div className="flex justify-between">
                        <span>{entry.lines}L</span>
                        <span>CC:{entry.maxComplexity}</span>
                      </div>
                      {entry.maintenanceBurden >= 50 && (
                        <div className="flex items-center gap-0.5 text-orange-400">
                          <Flame className="w-2.5 h-2.5" />
                          <span className="font-bold">{entry.maintenanceBurden}%</span>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {!heatmapLoading && heatmapData.length === 0 && (
            <div className="text-center py-12 text-white/30">
              <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>No files scanned yet. Select a project above.</p>
            </div>
          )}

          {/* Top complex files table */}
          {heatmapData.length > 0 && (
            <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <h3 className="font-semibold text-sm">Hot Spots</h3>
                <span className="text-xs text-white/30">{heatmapData.length} files scanned</span>
              </div>
              <div className="divide-y divide-white/5">
                {heatmapData.filter(e => e.maintenanceBurden >= 30).slice(0, 10).map((entry, i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-2.5 hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${burdenColor(entry.maintenanceBurden)}`} />
                      <span className="text-sm truncate text-white/70">{entry.filePath}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-white/40 shrink-0">
                      <span>{entry.lines}L</span>
                      <span>{entry.functions}fn</span>
                      <span className={entry.maxComplexity > 15 ? 'text-red-400 font-bold' : entry.maxComplexity > 8 ? 'text-orange-400' : ''}>
                        CC:{entry.maxComplexity}
                      </span>
                      <span className={entry.maxNesting > 4 ? 'text-red-400' : ''}>
                        D:{entry.maxNesting}
                      </span>
                      <div className="w-16 bg-white/5 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${burdenColor(entry.maintenanceBurden)}`}
                          style={{ width: `${Math.min(entry.maintenanceBurden, 100)}%` }}
                        />
                      </div>
                      <span className="w-8 text-right font-mono">{entry.maintenanceBurden}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Grid view ─────────────────────────────────────────────── */}
      {!loading && viewMode === 'grid' && filtered.length > 0 && (
        <div className="grid grid-cols-3 gap-6">
          {filtered.map((project) => (
            <div
              key={project.id}
              onClick={() => openProject(project)}
              className="bg-white/5 border border-white/10 rounded-xl p-6 hover:bg-white/10 transition-all cursor-pointer group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-white/10 to-white/5 rounded-xl flex items-center justify-center">
                  <FolderGit2 className="w-6 h-6 text-white/70" />
                </div>
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ring-2 ${healthRing(project.healthScore)} ${healthColor(project.healthScore)}`}>
                  <span className="text-sm font-bold">{project.healthScore}</span>
                </div>
              </div>
              <h3 className="font-semibold mb-1 group-hover:text-emerald-400 transition-colors">{project.name}</h3>
              <p className="text-sm text-white/50 mb-4 line-clamp-2">{project.description || project.path}</p>

              <div className="flex items-center gap-3 text-xs text-white/40 mb-4">
                <span className="flex items-center gap-1"><FileCode className="w-3 h-3" />{project.totalFiles} files</span>
                <span>{project.totalSymbols} symbols</span>
              </div>

              {project.languages.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-4">
                  {project.languages.slice(0, 3).map(lang => (
                    <span key={lang} className="px-2 py-0.5 bg-white/5 rounded text-xs text-white/50">{lang}</span>
                  ))}
                </div>
              )}

              {/* Language distribution bar */}
              {langDist[project.id] && langDist[project.id].length > 0 && (
                <div className="mb-3">
                  <div className="flex h-1.5 rounded-full overflow-hidden bg-white/5">
                    {langDist[project.id].map((l, idx) => (
                      <div
                        key={idx}
                        style={{ width: `${l.linePercent}%`, backgroundColor: langColors[l.language] || '#666' }}
                        title={`${l.language}: ${l.linePercent}% (${l.lines.toLocaleString()} lines)`}
                        className="transition-all"
                      />
                    ))}
                  </div>
                  <div className="flex gap-2 mt-1.5 flex-wrap">
                    {langDist[project.id].slice(0, 4).map((l, idx) => (
                      <span key={idx} className="text-[9px] text-white/30 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: langColors[l.language] || '#666' }} />
                        {l.language} {l.linePercent}%
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between text-xs text-white/30 pt-3 border-t border-white/5">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{timeSince(project.lastIndexedAt)}</span>
                <div className="flex gap-1">
                  <button onClick={(e) => handleReindex(project.id, e)} className="p-1.5 hover:bg-white/10 rounded transition-colors" title="Re-index">
                    <RefreshCw className={`w-3 h-3 ${reindexing.has(project.id) ? 'animate-spin' : ''}`} />
                  </button>
                  <button onClick={(e) => handleDelete(project.id, e)} className="p-1.5 hover:bg-red-500/20 rounded transition-colors text-red-400/50 hover:text-red-400" title="Delete">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}

          <button
            onClick={() => navigate('/new-project')}
            className="border-2 border-dashed border-white/10 rounded-xl p-6 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all flex flex-col items-center justify-center gap-3 text-white/40 hover:text-emerald-400"
          >
            <Plus className="w-8 h-8" />
            <span className="font-medium">Add New Project</span>
          </button>
        </div>
      )}

      {/* ── List view ─────────────────────────────────────────────── */}
      {!loading && viewMode === 'list' && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((project) => (
            <div
              key={project.id}
              onClick={() => openProject(project)}
              className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors cursor-pointer group"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gradient-to-br from-white/10 to-white/5 rounded-lg flex items-center justify-center">
                  <FolderGit2 className="w-5 h-5 text-white/70" />
                </div>
                <div>
                  <h3 className="font-medium group-hover:text-emerald-400 transition-colors">{project.name}</h3>
                  <p className="text-sm text-white/50">{project.description || project.path}</p>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <span className="text-xs text-white/40">{project.totalFiles} files</span>
                {project.languages.length > 0 && (
                  <span className="text-xs text-white/40">{project.languages.slice(0, 2).join(', ')}</span>
                )}
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${healthColor(project.healthScore)}`}>
                  {project.healthScore}%
                </div>
                <span className="text-xs text-white/40 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {timeSince(project.lastIndexedAt)}
                </span>
                <div className="flex gap-1">
                  <button onClick={(e) => handleReindex(project.id, e)} className="p-1.5 hover:bg-white/10 rounded" title="Re-index">
                    <RefreshCw className={`w-3 h-3 text-white/40 ${reindexing.has(project.id) ? 'animate-spin' : ''}`} />
                  </button>
                  <button onClick={(e) => handleDelete(project.id, e)} className="p-1.5 hover:bg-red-500/20 rounded text-red-400/50 hover:text-red-400" title="Delete">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
                <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-white/60" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
