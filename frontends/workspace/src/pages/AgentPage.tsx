import { useNavigate } from 'react-router-dom'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../AuthContext'
import {
  Brain,
  Square,
  Code2,
  GitCommit,
  CheckCircle2,
  Clock,
  Loader2,
  Sparkles,
  FolderGit2,
  ShieldAlert,
  XCircle,
  RefreshCw,
  ArrowRight,
  Shield,
  Swords,
  Zap,
  HeartPulse,
  ThumbsUp,
  ChevronDown,
  ChevronUp,
  Octagon,
  ShieldCheck,
} from 'lucide-react'

const API = '/api/v1'
const GUARDIAN_STORAGE_KEY = 'guardian_gauntlet_status'

interface SubTask {
  id: string
  agent_type: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  result?: string
  error?: string
  duration_ms?: number
}

interface SwarmGraph {
  id: string
  goal: string
  tasks: SubTask[]
  task_count: number
  completed_count: number
  failed_count: number
  progress: number
  is_complete: boolean
  is_success: boolean
  duration_ms: number
}

interface SwarmEvent {
  event: string
  task_id?: string
  agent_type?: string
  status?: string
  message?: string
  timestamp?: number
}

function statusIcon(status: string) {
  switch (status) {
    case 'running': return <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
    case 'completed': return <CheckCircle2 className="w-5 h-5 text-emerald-400" />
    case 'failed': return <XCircle className="w-5 h-5 text-red-400" />
    case 'skipped': return <Clock className="w-5 h-5 text-white/30" />
    default: return <Clock className="w-5 h-5 text-white/40" />
  }
}

function statusColor(status: string) {
  switch (status) {
    case 'running': return 'text-purple-400'
    case 'completed': return 'text-emerald-400'
    case 'failed': return 'text-red-400'
    default: return 'text-white/40'
  }
}

function agentLabel(type: string) {
  const labels: Record<string, string> = {
    graph: 'Knowledge Graph', vision: 'Vision Analyzer', migration: 'Migration',
    critic: 'Code Critic', heal: 'Heal Agent', sentinel: 'Sentinel',
    optimizer: 'Optimizer', forge: 'Recipe Forge', chief: 'Chief Architect',
    nexus: 'Nexus Analyzer',
  }
  return labels[type] || type
}

interface DebateRound {
  round: number
  profiler: { agent: string; role: string; argument: string }
  healer: { agent: string; role: string; argument: string }
}

interface DebateResult {
  topic: string
  rounds: DebateRound[]
  totalRounds: number
  consensusAreas: string[]
  recommendation: string
}

function DebateSection({ token }: { token: string | null }) {
  const [topic, setTopic] = useState('')
  const [debate, setDebate] = useState<DebateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(true)
  const [votes, setVotes] = useState<Record<number, 'profiler' | 'healer'>>({})

  const startDebate = async () => {
    if (!topic.trim() || loading) return
    setLoading(true)
    setDebate(null)
    setVotes({})
    try {
      const res = await fetch(`${API}/swarm/debate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ topic, rounds: 3 }),
      })
      if (res.ok) {
        const data = await res.json()
        setDebate(data)
      }
    } catch {}
    setLoading(false)
  }

  const profilerVotes = Object.values(votes).filter(v => v === 'profiler').length
  const healerVotes = Object.values(votes).filter(v => v === 'healer').length

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Swords className="w-5 h-5 text-orange-400" />
          Agent Debate (The Jury)
        </h2>
        {expanded ? <ChevronUp className="w-4 h-4 text-white/40" /> : <ChevronDown className="w-4 h-4 text-white/40" />}
      </button>

      {expanded && (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-white/40">
            When a refactor involves trade-offs, the Profiler Agent and Heal Agent debate the best approach. You cast the deciding vote.
          </p>
          <div className="flex gap-2">
            <input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && startDebate()}
              placeholder="e.g., Should we optimize this loop or keep it readable?"
              className="flex-1 px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-orange-500/50"
            />
            <button
              onClick={startDebate}
              disabled={!topic.trim() || loading}
              className="px-4 py-2 bg-orange-600 hover:bg-orange-500 rounded-lg text-sm font-medium disabled:opacity-40 transition-colors flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Swords className="w-4 h-4" />}
              Debate
            </button>
          </div>

          {debate && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-2 px-2 py-1 rounded bg-blue-500/10">
                  <Zap className="w-3 h-3 text-blue-400" />
                  <span className="text-blue-400 font-medium">Profiler Agent</span>
                  <span className="text-blue-400/60">{profilerVotes} votes</span>
                </div>
                <span className="text-white/30">vs</span>
                <div className="flex items-center gap-2 px-2 py-1 rounded bg-emerald-500/10">
                  <HeartPulse className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Heal Agent</span>
                  <span className="text-emerald-400/60">{healerVotes} votes</span>
                </div>
              </div>

              {debate.rounds.map(round => (
                <div key={round.round} className="space-y-2">
                  <p className="text-xs font-semibold text-white/40 uppercase tracking-wider">Round {round.round}</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className={`p-3 rounded-lg border transition-colors ${
                      votes[round.round] === 'profiler'
                        ? 'bg-blue-500/15 border-blue-500/40'
                        : 'bg-blue-500/5 border-blue-500/10'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        <Zap className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-xs font-semibold text-blue-300">{round.profiler.role}</span>
                      </div>
                      <p className="text-xs text-white/60 leading-relaxed">{round.profiler.argument}</p>
                      <button
                        onClick={() => setVotes(prev => ({ ...prev, [round.round]: 'profiler' }))}
                        className={`mt-2 flex items-center gap-1 text-[11px] px-2 py-1 rounded transition-colors ${
                          votes[round.round] === 'profiler'
                            ? 'bg-blue-500/30 text-blue-300'
                            : 'text-white/30 hover:text-blue-400 hover:bg-blue-500/10'
                        }`}
                      >
                        <ThumbsUp className="w-3 h-3" /> Vote
                      </button>
                    </div>
                    <div className={`p-3 rounded-lg border transition-colors ${
                      votes[round.round] === 'healer'
                        ? 'bg-emerald-500/15 border-emerald-500/40'
                        : 'bg-emerald-500/5 border-emerald-500/10'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        <HeartPulse className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-xs font-semibold text-emerald-300">{round.healer.role}</span>
                      </div>
                      <p className="text-xs text-white/60 leading-relaxed">{round.healer.argument}</p>
                      <button
                        onClick={() => setVotes(prev => ({ ...prev, [round.round]: 'healer' }))}
                        className={`mt-2 flex items-center gap-1 text-[11px] px-2 py-1 rounded transition-colors ${
                          votes[round.round] === 'healer'
                            ? 'bg-emerald-500/30 text-emerald-300'
                            : 'text-white/30 hover:text-emerald-400 hover:bg-emerald-500/10'
                        }`}
                      >
                        <ThumbsUp className="w-3 h-3" /> Vote
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              {debate.consensusAreas.length > 0 && (
                <div className="bg-white/5 rounded-lg p-3">
                  <p className="text-xs font-semibold text-white/50 mb-2">Consensus Areas</p>
                  {debate.consensusAreas.map((area, i) => (
                    <p key={i} className="text-xs text-white/40 flex items-start gap-2 mb-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400 mt-0.5 flex-shrink-0" />
                      {area}
                    </p>
                  ))}
                </div>
              )}

              <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3">
                <p className="text-xs font-semibold text-orange-300 mb-1">Final Recommendation</p>
                <p className="text-xs text-white/60">{debate.recommendation}</p>
                {Object.keys(votes).length > 0 && (
                  <p className="text-xs text-orange-400/70 mt-2">
                    Your verdict: {profilerVotes > healerVotes ? 'Performance' : healerVotes > profilerVotes ? 'Readability' : 'Split decision'}
                    {' '}({profilerVotes} Profiler / {healerVotes} Healer)
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AgentPage() {
  const navigate = useNavigate()
  const { token } = useAuth()
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  const [prompt, setPrompt] = useState('')
  const [workspacePath, setWorkspacePath] = useState(() =>
    localStorage.getItem('code4u_workspace') || ''
  )

  // Swarm state
  const [_graphId, setGraphId] = useState<string | null>(null)
  const [graph, setGraph] = useState<SwarmGraph | null>(null)
  const [events, setEvents] = useState<SwarmEvent[]>([])
  const [agentStatus, setAgentStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // History
  const [recentRuns, setRecentRuns] = useState<any[]>([])

  // Quality Gate (No-Pass, No-Push) — synced with Guardian
  const [gauntletPassed, setGauntletPassed] = useState(() =>
    localStorage.getItem(GUARDIAN_STORAGE_KEY) === 'passed'
  )
  const isGateBlocked = !gauntletPassed

  useEffect(() => {
    const sync = () => setGauntletPassed(localStorage.getItem(GUARDIAN_STORAGE_KEY) === 'passed')
    sync()
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Fetch recent runs on mount
  useEffect(() => {
    fetch(`${API}/swarm?limit=5`, { headers }).then(r => r.json()).then(d => {
      if (d.graphs) setRecentRuns(d.graphs)
    }).catch(() => {})
  }, [])

  // Polling for swarm status
  const startPolling = useCallback((id: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current)

    const poll = async () => {
      try {
        const res = await fetch(`${API}/swarm/${id}`, { headers })
        if (!res.ok) return
        const data = await res.json()
        if (data.graph) {
          const g = data.graph as SwarmGraph
          setGraph(g)
          if (data.events) setEvents(data.events)
          if (g.is_complete) {
            setAgentStatus(g.is_success ? 'completed' : 'failed')
            if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
          }
        }
      } catch {}
    }

    poll()
    pollingRef.current = setInterval(poll, 2000)
  }, [token])

  useEffect(() => {
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [])

  // Execute swarm
  const executeSwarm = async () => {
    if (!prompt.trim() || submitting) return
    setError('')
    setGraph(null)
    setEvents([])
    setSubmitting(true)
    setAgentStatus('running')

    try {
      // First, run a Sentinel scan to check for no-ai-zones
      if (workspacePath) {
        const sentinelRes = await fetch(`${API}/sentinel/scan`, {
          method: 'POST', headers,
          body: JSON.stringify({ workspacePath }),
        })
        if (sentinelRes.ok) {
          const sentinelData = await sentinelRes.json()
          if (sentinelData.violations?.length > 0) {
            const critical = sentinelData.violations.filter((v: any) => v.severity === 'critical')
            if (critical.length > 0) {
              setError(`Security Blocked: ${critical.length} critical violation(s) found. ${critical[0]?.message || 'Protected zone detected.'}`)
              setAgentStatus('failed')
              setSubmitting(false)
              return
            }
          }
        }
      }

      const res = await fetch(`${API}/swarm/execute`, {
        method: 'POST', headers,
        body: JSON.stringify({
          goal: prompt,
          workspacePath,
          context: {},
        }),
      })

      if (res.status === 403) {
        const data = await res.json().catch(() => ({}))
        setError(`Security Violation: ${data.detail || 'This action was blocked by the Sentinel.'}`)
        setAgentStatus('failed')
        setSubmitting(false)
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Swarm execution failed (${res.status})`)
      }

      const data = await res.json()
      const g = data.graph as SwarmGraph
      setGraph(g)
      setGraphId(g.id)
      if (data.events) setEvents(data.events)

      if (g.is_complete) {
        setAgentStatus(g.is_success ? 'completed' : 'failed')
      } else {
        startPolling(g.id)
      }
    } catch (e: any) {
      setError(e.message)
      setAgentStatus('failed')
    } finally {
      setSubmitting(false)
      setPrompt('')
    }
  }

  const [killing, setKilling] = useState(false)
  const [killResult, setKillResult] = useState<any>(null)

  const handleStop = () => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
    setAgentStatus('idle')
  }

  const handleEmergencyKill = async () => {
    setKilling(true)
    try {
      const r = await fetch(`${API}/swarm/kill-all`, { method: 'POST', headers })
      if (r.ok) {
        const data = await r.json()
        setKillResult(data)
        handleStop()
        setGraph(null)
        setEvents([])
        setError('')
        setGraphId(null)
        setAgentStatus('idle')
        setTimeout(() => setKillResult(null), 5000)
      }
    } catch {}
    setKilling(false)
  }

  const handleReset = () => {
    handleStop()
    setGraph(null)
    setEvents([])
    setError('')
    setGraphId(null)
    setKillResult(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI Agent</h1>
          <p className="text-white/50">Multi-agent swarm orchestration — plan, validate, execute</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            data-tour="emergency-stop"
            onClick={handleEmergencyKill}
            disabled={killing}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg font-bold text-sm hover:bg-red-500 transition-colors shadow-lg shadow-red-600/30 border border-red-500/50 disabled:opacity-50"
            title="Kill ALL active swarm tasks immediately"
          >
            <Octagon className="w-4 h-4" /> {killing ? 'KILLING...' : 'EMERGENCY STOP'}
          </button>
          {agentStatus === 'running' && (
            <button onClick={handleStop} className="flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg font-medium hover:bg-red-500/30 transition-colors">
              <Square className="w-4 h-4" /> Stop
            </button>
          )}
          {(agentStatus === 'completed' || agentStatus === 'failed') && (
            <button onClick={handleReset} className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-lg font-medium hover:bg-white/20 transition-colors">
              <RefreshCw className="w-4 h-4" /> New Task
            </button>
          )}
        </div>
      </div>

      {killResult && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center justify-between animate-pulse">
          <div className="flex items-center gap-3">
            <Octagon className="w-5 h-5 text-red-400" />
            <div>
              <p className="font-semibold text-red-400 text-sm">Emergency Stop Executed</p>
              <p className="text-xs text-white/50">
                {killResult.killedGraphs} graph(s) killed, {killResult.cancelledTasks} task(s) cancelled
                {killResult.terminatedPids?.length > 0 && `, ${killResult.terminatedPids.length} process(es) terminated`}
              </p>
            </div>
          </div>
          <button onClick={() => setKillResult(null)} className="text-white/40 hover:text-white/70 text-sm">Dismiss</button>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Main Panel */}
        <div className="col-span-2 space-y-6">
          {/* Prompt Input */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-400" />
              Give Agent Instructions
            </h2>
            <div className="space-y-4">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={`Describe what you want the swarm to do...\n\nExamples:\n• "Refactor all exports in the utils folder"\n• "Add error handling to all API routes"\n• "Standardize logging across the codebase"`}
                className="w-full h-32 px-4 py-3 bg-black/40 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50 resize-none"
                disabled={agentStatus === 'running'}
              />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-white/50">
                  <FolderGit2 className="w-4 h-4" />
                  <input
                    value={workspacePath}
                    onChange={(e) => { setWorkspacePath(e.target.value); localStorage.setItem('code4u_workspace', e.target.value) }}
                    placeholder="/path/to/workspace"
                    className="bg-transparent border-b border-white/10 focus:border-purple-400 focus:outline-none text-sm font-mono w-64"
                    disabled={agentStatus === 'running'}
                  />
                </div>
                <button
                  onClick={executeSwarm}
                  disabled={!prompt.trim() || agentStatus === 'running' || !workspacePath}
                  className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-purple-500/25 transition-all"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {submitting ? 'Starting...' : 'Start Agent'}
                </button>
              </div>
            </div>
          </div>

          {/* Error / Security Block */}
          {error && (
            <div className={`border rounded-xl p-4 flex items-start gap-3 ${
              error.startsWith('Security') ? 'bg-amber-500/10 border-amber-500/30' : 'bg-red-500/10 border-red-500/30'
            }`}>
              {error.startsWith('Security') ? (
                <ShieldAlert className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
              ) : (
                <XCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
              )}
              <div>
                <p className={`text-sm font-medium ${error.startsWith('Security') ? 'text-amber-400' : 'text-red-400'}`}>
                  {error.startsWith('Security') ? 'Sentinel Blocked' : 'Execution Failed'}
                </p>
                <p className={`text-xs mt-1 ${error.startsWith('Security') ? 'text-amber-400/70' : 'text-red-400/70'}`}>{error}</p>
              </div>
            </div>
          )}

          {/* Task Graph */}
          {graph && (
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Task Graph</h2>
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-white/50">{graph.completed_count}/{graph.task_count} tasks</span>
                  {graph.is_complete && graph.is_success && (
                    <span className="flex items-center gap-1 text-emerald-400"><CheckCircle2 className="w-4 h-4" /> Success</span>
                  )}
                  {graph.is_complete && !graph.is_success && (
                    <span className="flex items-center gap-1 text-red-400"><XCircle className="w-4 h-4" /> Failed</span>
                  )}
                  {!graph.is_complete && (
                    <span className="flex items-center gap-1 text-purple-400"><Loader2 className="w-4 h-4 animate-spin" /> Running</span>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              <div className="h-2 bg-white/10 rounded-full overflow-hidden mb-6">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    graph.is_complete && !graph.is_success ? 'bg-red-500' : 'bg-gradient-to-r from-purple-500 to-emerald-500'
                  }`}
                  style={{ width: `${Math.round(graph.progress * 100)}%` }}
                />
              </div>

              {/* Task list */}
              <div className="space-y-3">
                {graph.tasks?.map((task) => (
                  <div key={task.id} className="p-4 bg-black/30 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {statusIcon(task.status)}
                        <div>
                          <span className="font-medium">{task.description}</span>
                          <span className="ml-2 text-xs px-2 py-0.5 rounded bg-white/5 text-white/40">
                            {agentLabel(task.agent_type)}
                          </span>
                        </div>
                      </div>
                      <span className={`text-sm ${statusColor(task.status)}`}>
                        {task.status}
                        {task.duration_ms ? ` (${(task.duration_ms / 1000).toFixed(1)}s)` : ''}
                      </span>
                    </div>
                    {task.error && (
                      <p className="mt-2 text-xs text-red-400/70 font-mono">{task.error}</p>
                    )}
                    {task.result && task.status === 'completed' && (
                      <p className="mt-2 text-xs text-white/40 truncate">{task.result}</p>
                    )}
                  </div>
                ))}
              </div>

              {/* Duration */}
              {graph.is_complete && (
                <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-sm text-white/50">
                  <span>Total duration: {(graph.duration_ms / 1000).toFixed(2)}s</span>
                  <button
                    onClick={() => navigate('/refactor')}
                    disabled={isGateBlocked}
                    className={`flex items-center gap-1 transition-colors ${
                      isGateBlocked ? 'text-white/30 cursor-not-allowed' : 'text-amber-400 hover:text-amber-300'
                    }`}
                  >
                    View in Refactor <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Quality Gate (No-Pass, No-Push) */}
          <div
            className={`rounded-xl p-4 flex items-center justify-between ${
              isGateBlocked
                ? 'bg-red-500/10 border border-red-500/30'
                : 'bg-emerald-500/10 border border-emerald-500/30'
            }`}
          >
            <div className="flex items-center gap-3">
              {isGateBlocked ? (
                <ShieldAlert className="w-5 h-5 text-red-400 shrink-0" />
              ) : (
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
              )}
              <div>
                <p className={`font-semibold text-sm ${isGateBlocked ? 'text-red-400' : 'text-emerald-400'}`}>
                  {isGateBlocked
                    ? 'Security/Quality Gate: BLOCKED — Run the Guardian Gauntlet before applying changes'
                    : 'Quality Gate: PASSED — Changes verified through 5-stage recursive gauntlet'}
                </p>
              </div>
            </div>
            <button
              onClick={() => navigate('/guardian')}
              className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/15 rounded-lg font-medium text-sm transition-colors"
            >
              <Shield className="w-4 h-4" />
              {isGateBlocked ? 'Run Guardian' : 'Guardian'}
            </button>
          </div>

          {/* Agent Debate */}
          <DebateSection token={token} />
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* Agent Status */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Agent Status</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-white/60">Status</span>
                <span className={`flex items-center gap-2 ${
                  agentStatus === 'running' ? 'text-purple-400' :
                  agentStatus === 'completed' ? 'text-emerald-400' :
                  agentStatus === 'failed' ? 'text-red-400' : 'text-white/50'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    agentStatus === 'running' ? 'bg-purple-400 animate-pulse' :
                    agentStatus === 'completed' ? 'bg-emerald-400' :
                    agentStatus === 'failed' ? 'bg-red-400' : 'bg-white/30'
                  }`} />
                  {agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)}
                </span>
              </div>
              {graph && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-white/60">Tasks</span>
                    <span>{graph.completed_count}/{graph.task_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/60">Failed</span>
                    <span className={graph.failed_count > 0 ? 'text-red-400' : ''}>{graph.failed_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/60">Duration</span>
                    <span>{(graph.duration_ms / 1000).toFixed(1)}s</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Event Log */}
          {events.length > 0 && (
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4">Activity Log</h2>
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {events.slice(-10).reverse().map((evt, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <Code2 className="w-4 h-4 text-white/40 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-white/80 text-xs">{evt.event}: {evt.message || evt.agent_type || evt.status || ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Runs */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Recent Runs</h2>
            <div className="space-y-2">
              {recentRuns.length === 0 && (
                <p className="text-sm text-white/40">No recent swarm runs</p>
              )}
              {recentRuns.map((run) => (
                <div key={run.id} className="flex items-center justify-between p-3 bg-black/30 rounded-lg text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    {run.isSuccess ? <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" /> : <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}
                    <span className="truncate text-white/70">{run.goal}</span>
                  </div>
                  <span className="text-xs text-white/40 flex-shrink-0 ml-2">{run.taskCount} tasks</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <button onClick={() => navigate('/ide')} className="w-full flex items-center gap-3 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-left">
                <Code2 className="w-4 h-4 text-emerald-400" /> <span>Open in IDE</span>
              </button>
              <button onClick={() => navigate('/refactor')} className="w-full flex items-center gap-3 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-left">
                <GitCommit className="w-4 h-4 text-amber-400" /> <span>Refactor Page</span>
              </button>
              <button onClick={() => navigate('/settings')} className="w-full flex items-center gap-3 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-left">
                <Shield className="w-4 h-4 text-blue-400" /> <span>Sentinel Rules</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
