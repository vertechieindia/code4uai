import { useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../AuthContext'
import {
  Github,
  GitBranch,
  Search,
  Lock,
  Globe,
  Star,
  Clock,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  FolderInput,
  FolderGit2,
  Link2,
  AlertCircle,
  User,
} from 'lucide-react'

const API = '/api/v1'

interface GitHubRepo {
  name: string
  full_name: string
  owner: string
  private: boolean
  clone_url: string
  html_url: string
  description: string
  language: string
  stars: number
  updated_at: string
  default_branch: string
}

export default function ConnectRepoPage() {
  const navigate = useNavigate()
  const { token } = useAuth()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const [selectedProvider, setSelectedProvider] = useState<'github' | 'gitlab' | 'bitbucket' | 'local' | 'url' | null>(null)
  const [importingRepo, setImportingRepo] = useState('')
  const [importPhase, setImportPhase] = useState<'idle' | 'cloning' | 'indexing' | 'done'>('idle')
  const [importError, setImportError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  // Local path import
  const [localPath, setLocalPath] = useState('')
  const [localName, setLocalName] = useState('')

  // URL clone import
  const [repoUrl, setRepoUrl] = useState('')
  const [urlName, setUrlName] = useState('')

  // GitHub OAuth state
  const [githubConnected, setGithubConnected] = useState(false)
  const [githubUsername, setGithubUsername] = useState('')
  const [githubAvatar, setGithubAvatar] = useState('')
  const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([])
  const [reposLoading, setReposLoading] = useState(false)
  const [oauthChecking, setOauthChecking] = useState(false)

  // Check GitHub connection status on mount
  useEffect(() => {
    const checkGithub = async () => {
      try {
        const res = await fetch(`${API}/auth/github/status`, { headers })
        if (res.ok) {
          const data = await res.json()
          if (data.connected) {
            setGithubConnected(true)
            setGithubUsername(data.github_username)
            setGithubAvatar(data.avatar_url)
          }
        }
      } catch {}
    }
    checkGithub()
  }, [])

  // Handle OAuth callback (check URL params)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    if (code) {
      setOauthChecking(true)
      fetch(`${API}/auth/github/callback?code=${code}&state=code4u`)
        .then(res => res.json())
        .then(data => {
          if (data.github_username) {
            setGithubConnected(true)
            setGithubUsername(data.github_username)
            setGithubAvatar(data.avatar_url || '')
            // Link to current user
            fetch(`${API}/auth/github/link`, { method: 'POST', headers }).catch(() => {})
          }
          window.history.replaceState({}, '', '/connect-repo')
        })
        .catch(() => {})
        .finally(() => setOauthChecking(false))
    }
  }, [])

  // Fetch repos when GitHub is connected and selected
  const fetchGithubRepos = useCallback(async () => {
    if (!githubConnected) return
    setReposLoading(true)
    try {
      const res = await fetch(`${API}/auth/github/repos?per_page=50`, { headers })
      if (res.ok) {
        const data = await res.json()
        setGithubRepos(data.repos || [])
      }
    } catch {}
    setReposLoading(false)
  }, [githubConnected])

  useEffect(() => {
    if (selectedProvider === 'github' && githubConnected) fetchGithubRepos()
  }, [selectedProvider, githubConnected, fetchGithubRepos])

  const startGithubOAuth = async () => {
    try {
      const res = await fetch(`${API}/auth/github/login`)
      if (res.ok) {
        const data = await res.json()
        if (data.url) {
          window.location.href = data.url
        } else if (data.clientId) {
          window.location.href = `https://github.com/login/oauth/authorize?client_id=${data.clientId}&scope=repo read:user user:email&state=code4u`
        }
      } else {
        setImportError('GitHub OAuth not configured on the server.')
      }
    } catch {
      setImportError('Failed to start GitHub OAuth.')
    }
  }

  const providers = [
    { id: 'local' as const, name: 'Local Folder', icon: FolderInput, color: 'from-emerald-500 to-cyan-500', status: 'ready' },
    { id: 'url' as const, name: 'Git URL', icon: Link2, color: 'from-violet-500 to-purple-500', status: 'ready' },
    { id: 'github' as const, name: 'GitHub', icon: Github, color: 'from-gray-700 to-gray-900', status: githubConnected ? 'connected' : 'connect' },
    { id: 'gitlab' as const, name: 'GitLab', icon: () => <span className="text-2xl">🦊</span>, color: 'from-orange-500 to-red-500', status: 'soon' },
  ]

  const importLocalFolder = async () => {
    if (!localPath.trim()) return
    setImportError('')
    setImportPhase('indexing')
    setImportingRepo(localPath)

    try {
      const name = localName.trim() || localPath.split('/').filter(Boolean).pop() || 'project'
      const res = await fetch(`${API}/projects`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name, path: localPath, description: `Imported from ${localPath}` }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Import failed (${res.status})`)
      }
      const project = await res.json()
      setImportPhase('done')
      setTimeout(() => {
        localStorage.setItem('code4u_workspace', project.path)
        navigate('/ide')
      }, 1500)
    } catch (e: any) {
      setImportError(e.message)
      setImportPhase('idle')
    }
  }

  const importFromUrl = async () => {
    if (!repoUrl.trim()) return
    setImportError('')
    setImportPhase('cloning')
    setImportingRepo(repoUrl)

    try {
      const urlParts = repoUrl.replace(/\.git$/, '').split('/')
      const name = urlName.trim() || urlParts[urlParts.length - 1] || 'repo'
      const owner = urlParts[urlParts.length - 2] || 'unknown'

      const res = await fetch(`${API}/projects`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name,
          path: `/tmp/code4u-repos/${owner}/${name}`,
          description: `Cloned from ${repoUrl}`,
          repoUrl: repoUrl,
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Clone failed')
      }

      const project = await res.json()
      setImportPhase('done')
      setTimeout(() => {
        localStorage.setItem('code4u_workspace', project.path)
        navigate('/ide')
      }, 1500)
    } catch (e: any) {
      setImportError(e.message)
      setImportPhase('idle')
    }
  }

  const importGitHubRepo = async (repo: GitHubRepo) => {
    setImportError('')
    setImportPhase('cloning')
    setImportingRepo(repo.full_name)

    try {
      const res = await fetch(`${API}/projects`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name: repo.name,
          path: `/tmp/code4u-repos/${repo.owner}/${repo.name}`,
          description: repo.description || `Cloned from GitHub: ${repo.full_name}`,
          repoUrl: repo.clone_url,
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Clone failed')
      }

      const project = await res.json()
      setImportPhase('done')
      setTimeout(() => {
        localStorage.setItem('code4u_workspace', project.path)
        navigate('/ide')
      }, 1500)
    } catch (e: any) {
      setImportError(e.message)
      setImportPhase('idle')
    }
  }

  const filteredRepos = githubRepos.filter(r =>
    r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    r.full_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const statusBadge = (status: string) => {
    if (status === 'connected') return <span className="text-sm text-emerald-400">✓ Connected</span>
    if (status === 'connect') return <span className="text-sm text-amber-400">Connect</span>
    if (status === 'ready') return <span className="text-sm text-emerald-400">✓ Ready</span>
    return <span className="text-sm text-white/40">Coming soon</span>
  }

  const formatDate = (d: string) => {
    if (!d) return ''
    const diff = Date.now() - new Date(d).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/')} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Connect Repository</h1>
          <p className="text-white/50">Import from a local folder, Git URL, or connect your GitHub account</p>
        </div>
      </div>

      {/* OAuth checking banner */}
      {oauthChecking && (
        <div className="flex items-center gap-3 p-4 bg-violet-500/10 border border-violet-500/20 rounded-xl">
          <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
          <span className="text-sm text-violet-400">Connecting GitHub account...</span>
        </div>
      )}

      {/* Provider Selection */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Select Source</h2>
        <div className="grid grid-cols-4 gap-4">
          {providers.map((provider) => (
            <button
              key={provider.id}
              onClick={() => {
                if (provider.status === 'soon') return
                if (provider.id === 'github' && !githubConnected) {
                  startGithubOAuth()
                  return
                }
                setSelectedProvider(provider.id)
                setImportPhase('idle')
                setImportError('')
              }}
              className={`p-6 rounded-xl border transition-all ${
                selectedProvider === provider.id
                  ? 'border-emerald-500 bg-emerald-500/10'
                  : provider.status === 'soon'
                    ? 'border-white/5 bg-white/[0.02] opacity-50 cursor-not-allowed'
                    : 'border-white/10 bg-white/5 hover:bg-white/10'
              }`}
            >
              <div className={`w-12 h-12 bg-gradient-to-br ${provider.color} rounded-xl flex items-center justify-center mb-4`}>
                {(() => { const Icon = provider.icon as any; return <Icon className="w-6 h-6 text-white" /> })()}
              </div>
              <h3 className="font-semibold mb-1">{provider.name}</h3>
              {statusBadge(provider.status)}
            </button>
          ))}
        </div>
      </div>

      {/* GitHub Connected Banner */}
      {githubConnected && selectedProvider === 'github' && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 flex items-center gap-3">
          {githubAvatar ? (
            <img src={githubAvatar} className="w-10 h-10 rounded-full" alt="" />
          ) : (
            <User className="w-10 h-10 text-emerald-400" />
          )}
          <div>
            <p className="text-sm font-medium text-emerald-400">Connected as @{githubUsername}</p>
            <p className="text-xs text-emerald-400/60">Select a repository below to clone and index</p>
          </div>
        </div>
      )}

      {/* Local Folder Import */}
      {selectedProvider === 'local' && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-emerald-400" />
            Import Local Folder
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5">Project Name</label>
              <input
                type="text" value={localName} onChange={(e) => setLocalName(e.target.value)}
                placeholder="my-awesome-project" disabled={importPhase !== 'idle'}
                className="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-sm focus:outline-none focus:border-emerald-500/50 disabled:opacity-50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5">Absolute Path</label>
              <input
                type="text" value={localPath} onChange={(e) => setLocalPath(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && importLocalFolder()}
                placeholder="/Users/you/projects/my-app" disabled={importPhase !== 'idle'}
                className="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-sm font-mono focus:outline-none focus:border-emerald-500/50 disabled:opacity-50"
                autoFocus
              />
            </div>
            <ProgressBanner phase={importPhase} error={importError} />
            <button
              onClick={importLocalFolder}
              disabled={!localPath.trim() || importPhase !== 'idle'}
              className="w-full py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
            >
              {importPhase === 'indexing' ? 'Indexing...' : importPhase === 'done' ? 'Done!' : 'Import & Index'}
            </button>
          </div>
        </div>
      )}

      {/* Git URL Clone */}
      {selectedProvider === 'url' && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Link2 className="w-5 h-5 text-violet-400" />
            Clone from Git URL
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5">Repository URL</label>
              <input
                type="text" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && importFromUrl()}
                placeholder="https://github.com/owner/repo.git" disabled={importPhase !== 'idle'}
                className="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-sm font-mono focus:outline-none focus:border-violet-500/50 disabled:opacity-50"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5">Project Name (optional)</label>
              <input
                type="text" value={urlName} onChange={(e) => setUrlName(e.target.value)}
                placeholder="auto-detected from URL" disabled={importPhase !== 'idle'}
                className="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-sm focus:outline-none focus:border-violet-500/50 disabled:opacity-50"
              />
            </div>
            <ProgressBanner phase={importPhase} error={importError} />
            <button
              onClick={importFromUrl}
              disabled={!repoUrl.trim() || importPhase !== 'idle'}
              className="w-full py-3 bg-gradient-to-r from-violet-500 to-purple-500 rounded-xl font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-violet-500/25 transition-all"
            >
              {importPhase === 'cloning' ? 'Cloning...' : importPhase === 'indexing' ? 'Indexing...' : importPhase === 'done' ? 'Done!' : 'Clone & Index'}
            </button>
          </div>
        </div>
      )}

      {/* GitHub Repo List */}
      {selectedProvider === 'github' && githubConnected && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Your Repositories</h2>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
              <input
                type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search repositories..."
                className="w-64 pl-10 pr-4 py-2 bg-black/30 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-emerald-500/50"
              />
            </div>
          </div>

          <ProgressBanner phase={importPhase} error={importError} />

          {reposLoading && githubRepos.length === 0 && (
            <div className="flex items-center gap-2 p-6 text-sm text-white/50 justify-center">
              <Loader2 className="w-5 h-5 animate-spin" /> Loading repositories from GitHub...
            </div>
          )}

          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {filteredRepos.map((repo) => (
              <button
                key={repo.full_name}
                onClick={() => importGitHubRepo(repo)}
                disabled={importPhase !== 'idle'}
                className="w-full flex items-center justify-between p-4 bg-black/30 rounded-lg hover:bg-black/50 transition-colors text-left disabled:opacity-50"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-white/10 rounded-lg flex items-center justify-center">
                    <GitBranch className="w-5 h-5 text-white/70" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{repo.full_name}</span>
                      {repo.private ? <Lock className="w-3 h-3 text-white/40" /> : <Globe className="w-3 h-3 text-white/40" />}
                      {repo.language && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-white/10 rounded text-white/50">{repo.language}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-white/50">
                      {repo.description && <span className="truncate max-w-[300px]">{repo.description}</span>}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-white/30 mt-0.5">
                      {repo.stars > 0 && <span className="flex items-center gap-1"><Star className="w-3 h-3" />{repo.stars}</span>}
                      <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDate(repo.updated_at)}</span>
                      <span>{repo.default_branch}</span>
                    </div>
                  </div>
                </div>
                <div>
                  {importingRepo === repo.full_name && importPhase === 'cloning' ? (
                    <span className="flex items-center gap-2 text-xs text-violet-400">
                      <Loader2 className="w-4 h-4 animate-spin" /> Cloning...
                    </span>
                  ) : importingRepo === repo.full_name && importPhase === 'done' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <span className="px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded-lg text-sm font-medium">
                      Clone
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {!reposLoading && filteredRepos.length === 0 && githubRepos.length > 0 && (
            <p className="text-center text-sm text-white/40 p-4">No repositories match your search.</p>
          )}
        </div>
      )}
    </div>
  )
}

function ProgressBanner({ phase, error }: { phase: string; error: string }) {
  return (
    <>
      {phase === 'cloning' && (
        <div className="flex items-center gap-3 p-4 bg-violet-500/10 border border-violet-500/20 rounded-xl">
          <Loader2 className="w-5 h-5 text-violet-400 animate-spin flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-violet-400">Cloning repository...</p>
            <p className="text-xs text-violet-400/60">This may take a moment for large repos</p>
          </div>
        </div>
      )}
      {phase === 'indexing' && (
        <div className="flex items-center gap-3 p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl">
          <Loader2 className="w-5 h-5 text-purple-400 animate-spin flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-purple-400">Nexus Indexing in progress...</p>
            <p className="text-xs text-purple-400/60">Scanning symbols, building dependency graph</p>
          </div>
        </div>
      )}
      {phase === 'done' && (
        <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-emerald-400">Project indexed successfully!</p>
            <p className="text-xs text-emerald-400/60">Redirecting to IDE...</p>
          </div>
        </div>
      )}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <span className="text-sm text-red-400">{error}</span>
        </div>
      )}
    </>
  )
}
