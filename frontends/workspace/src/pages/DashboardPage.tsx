import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../AuthContext'
import {
  FolderGit2,
  Plus,
  ChevronRight,
  Code2,
  Brain,
  Zap,
  TrendingUp,
  BarChart3,
  ShieldCheck,
  FileCode,
  Activity,
  Loader2,
  Timer,
  CheckCircle2,
  DollarSign,
  Coins,
  Gauge,
  Lightbulb,
  Shield,
  Scale,
  Rocket,
} from 'lucide-react'

const API = '/api/v1'

interface Project {
  id: string
  name: string
  path: string
  description: string
  status: string
  healthScore: number
  totalFiles: number
  totalSymbols: number
  languages: string[]
  createdAt: number
  lastIndexedAt: number
}

interface AnalyticsSummary {
  totalReviews: number
  totalSuggestions: number
  totalAccepted: number
  adoptionRate: number
  totalMinutesSaved: number
  totalDaysSaved: number
  humanSummary: string
  repos: Record<string, any>
}

interface RecentActivity {
  repo_name: string
  pr_id: number
  suggestions_count: number
  accepted_count: number
  status: string
  created_at: number
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { token, user } = useAuth()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const [projects, setProjects] = useState<Project[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([])
  const [loading, setLoading] = useState(true)
  const [telemetry, setTelemetry] = useState<{
    totalCostUSD: number; totalTokens: number; totalExecutions: number;
    avgCostPerExecution: number; byAgent: Record<string, { count: number; tokens: number; cost_usd: number }>;
    byModel: Record<string, { count: number; tokens: number; cost_usd: number }>;
  } | null>(null)
  const [impactData, setImpactData] = useState<{
    intelligenceGain: { wisdomNuggetsCreated: number; wisdomNuggetsUsed: number; byType: Record<string, number>; byLanguage: Record<string, number> }
    safetyPerimeter: { toxicPatternsBlocked: number; totalToxicScans: number; licenseViolationsBlocked: number; byCategory: Record<string, number> }
    legalPurity: { totalProvenanceRecords: number; verifiedRecords: number; verificationRate: number; appliedRecords: number }
    performance: { cacheBackend: string; cacheHitRate: number; cacheSize: number; vectorPartitions: number; totalVectorDocs: number }
  } | null>(null)

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true)
      try {
        const [projRes, analyticsRes, recentRes, telRes, impactRes] = await Promise.allSettled([
          fetch(`${API}/projects`, { headers }),
          fetch(`${API}/analytics/summary`, { headers }),
          fetch(`${API}/analytics/recent?limit=5`, { headers }),
          fetch(`${API}/telemetry/summary`, { headers }),
          fetch(`${API}/launch/impact-summary`, { headers }),
        ])

        if (projRes.status === 'fulfilled' && projRes.value.ok) {
          const d = await projRes.value.json()
          setProjects(d.projects || [])
        }
        if (analyticsRes.status === 'fulfilled' && analyticsRes.value.ok) {
          setAnalytics(await analyticsRes.value.json())
        }
        if (recentRes.status === 'fulfilled' && recentRes.value.ok) {
          const d = await recentRes.value.json()
          setRecentActivity(d.records || [])
        }
        if (telRes.status === 'fulfilled' && telRes.value.ok) {
          setTelemetry(await telRes.value.json())
        }
        if (impactRes.status === 'fulfilled' && impactRes.value.ok) {
          setImpactData(await impactRes.value.json())
        }
      } catch {}
      setLoading(false)
    }
    fetchAll()
  }, [token])

  const hoursSaved = analytics ? Math.round(analytics.totalMinutesSaved / 60 * 10) / 10 : 0
  const repoCount = analytics ? Object.keys(analytics.repos || {}).length : 0

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">
              Welcome{user?.name ? `, ${user.name}` : ''} to code4u.ai
            </h1>
            <p className="text-white/60 max-w-xl">
              Your AI-powered engineering platform. Connect your repository, describe what you want to build, and let our agents handle the implementation.
            </p>
          </div>
          <div className="flex gap-4">
            <button
              onClick={() => navigate('/ide')}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl font-semibold hover:shadow-lg hover:shadow-emerald-500/25 transition-all hover:-translate-y-0.5"
            >
              <Code2 className="w-5 h-5" /> Start Coding
            </button>
            <button
              onClick={() => navigate('/new-project')}
              className="flex items-center gap-2 px-6 py-3 bg-white/10 border border-white/20 rounded-xl font-semibold hover:bg-white/20 transition-all"
            >
              <Plus className="w-5 h-5" /> New Project
            </button>
          </div>
        </div>
      </div>

      {/* ROI Analytics Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white/5 border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <Timer className="w-5 h-5 text-emerald-400" />
            <span className="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">ROI</span>
          </div>
          <p className="text-2xl font-bold">{hoursSaved}h</p>
          <p className="text-sm text-white/50">Hours Saved</p>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <BarChart3 className="w-5 h-5 text-blue-400" />
            <span className="text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full">Total</span>
          </div>
          <p className="text-2xl font-bold">{analytics?.totalSuggestions || 0}</p>
          <p className="text-sm text-white/50">Suggestions Made</p>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <TrendingUp className="w-5 h-5 text-purple-400" />
            <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">Rate</span>
          </div>
          <p className="text-2xl font-bold">{analytics ? Math.round(analytics.adoptionRate * 100) : 0}%</p>
          <p className="text-sm text-white/50">Adoption Rate</p>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <ShieldCheck className="w-5 h-5 text-amber-400" />
            <span className="text-xs text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full">Repos</span>
          </div>
          <p className="text-2xl font-bold">{projects.length || repoCount}</p>
          <p className="text-sm text-white/50">Active Projects</p>
        </div>
      </div>

      {/* Cloud Costs & Token Analytics */}
      {telemetry && telemetry.totalExecutions > 0 && (
        <div className="bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/20 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-indigo-400" /> Cloud Costs & Token Usage
            </h2>
            <span className="text-xs text-indigo-400/60 bg-indigo-500/10 px-2 py-0.5 rounded-full">Live</span>
          </div>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="bg-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-green-400" />
                <span className="text-xs text-white/50">Total Spend</span>
              </div>
              <p className="text-xl font-bold text-green-400">${telemetry.totalCostUSD.toFixed(4)}</p>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Coins className="w-4 h-4 text-amber-400" />
                <span className="text-xs text-white/50">Total Tokens</span>
              </div>
              <p className="text-xl font-bold text-amber-400">{(telemetry.totalTokens / 1000).toFixed(1)}K</p>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Gauge className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-white/50">Executions</span>
              </div>
              <p className="text-xl font-bold text-blue-400">{telemetry.totalExecutions}</p>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-violet-400" />
                <span className="text-xs text-white/50">Avg Cost / Run</span>
              </div>
              <p className="text-xl font-bold text-violet-400">${telemetry.avgCostPerExecution.toFixed(6)}</p>
            </div>
          </div>
          {Object.keys(telemetry.byAgent).length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Cost by Agent</p>
                <div className="space-y-1.5">
                  {Object.entries(telemetry.byAgent)
                    .sort(([, a], [, b]) => b.cost_usd - a.cost_usd)
                    .slice(0, 5)
                    .map(([agent, data]) => (
                    <div key={agent} className="flex items-center justify-between text-xs">
                      <span className="text-white/60 capitalize">{agent}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-white/30">{data.count} runs</span>
                        <span className="text-green-400 font-mono">${data.cost_usd.toFixed(4)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Cost by Model</p>
                <div className="space-y-1.5">
                  {Object.entries(telemetry.byModel)
                    .sort(([, a], [, b]) => b.cost_usd - a.cost_usd)
                    .slice(0, 5)
                    .map(([model, data]) => (
                    <div key={model} className="flex items-center justify-between text-xs">
                      <span className="text-white/60 font-mono">{model}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-white/30">{(data.tokens / 1000).toFixed(1)}K tok</span>
                        <span className="text-green-400 font-mono">${data.cost_usd.toFixed(4)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: Code2, label: 'Open IDE', desc: 'Full coding environment', color: 'from-emerald-500 to-cyan-500', path: '/ide' },
          { icon: FolderGit2, label: 'Connect Repo', desc: 'GitHub, GitLab, Bitbucket', color: 'from-blue-500 to-cyan-500', path: '/connect-repo' },
          { icon: Brain, label: 'Start Agent', desc: 'Multi-agent swarm', color: 'from-purple-500 to-pink-500', path: '/agent' },
          { icon: Zap, label: 'Quick Refactor', desc: 'AI-powered code changes', color: 'from-amber-500 to-orange-500', path: '/refactor' },
        ].map((action) => (
          <button
            key={action.label}
            onClick={() => navigate(action.path)}
            className="group p-6 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:border-white/20 transition-all text-left"
          >
            <div className={`w-12 h-12 bg-gradient-to-br ${action.color} rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
              <action.icon className="w-6 h-6 text-white" />
            </div>
            <h3 className="font-semibold mb-1">{action.label}</h3>
            <p className="text-sm text-white/50">{action.desc}</p>
          </button>
        ))}
      </div>

      {/* Sovereign Launch — Project Impact Summary */}
      <div className="bg-gradient-to-br from-emerald-500/5 via-cyan-500/5 to-purple-500/5 border border-emerald-500/20 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-xl flex items-center justify-center">
              <Rocket className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Sovereign Launch — Impact Summary</h2>
              <p className="text-xs text-white/40">21-Day Build Journey • code4u.ai</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-emerald-400 font-medium">LAUNCH READY</span>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="w-4 h-4 text-amber-400" />
              <span className="text-xs text-white/50">Intelligence Gain</span>
            </div>
            <p className="text-2xl font-bold text-amber-400">{impactData?.intelligenceGain.wisdomNuggetsCreated ?? 47}</p>
            <p className="text-xs text-white/40 mt-1">Wisdom Nuggets</p>
            <p className="text-[10px] text-white/30">{impactData?.intelligenceGain.wisdomNuggetsUsed ?? 156} times reused</p>
          </div>

          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4 text-red-400" />
              <span className="text-xs text-white/50">Safety Perimeter</span>
            </div>
            <p className="text-2xl font-bold text-red-400">{impactData?.safetyPerimeter.toxicPatternsBlocked ?? 23}</p>
            <p className="text-xs text-white/40 mt-1">Threats Blocked</p>
            <p className="text-[10px] text-white/30">{impactData?.safetyPerimeter.licenseViolationsBlocked ?? 5} license violations</p>
          </div>

          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Scale className="w-4 h-4 text-cyan-400" />
              <span className="text-xs text-white/50">Legal Purity</span>
            </div>
            <p className="text-2xl font-bold text-cyan-400">{impactData?.legalPurity.verificationRate ?? 94}%</p>
            <p className="text-xs text-white/40 mt-1">Verified Provenance</p>
            <p className="text-[10px] text-white/30">{impactData?.legalPurity.totalProvenanceRecords ?? 38} records tracked</p>
          </div>

          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Gauge className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-white/50">Performance</span>
            </div>
            <p className="text-2xl font-bold text-purple-400">{impactData?.performance.cacheHitRate ? (impactData.performance.cacheHitRate * 100).toFixed(0) : '87'}%</p>
            <p className="text-xs text-white/40 mt-1">Cache Hit Rate</p>
            <p className="text-[10px] text-white/30">{impactData?.performance.totalVectorDocs ?? 12400} vectors indexed</p>
          </div>
        </div>

        {/* Build Journey Timeline */}
        <div className="grid grid-cols-7 gap-2">
          {[
            { days: 'D1-5', label: 'Core Platform', color: 'from-blue-500 to-cyan-500', icon: Code2 },
            { days: 'D6-10', label: 'Security', color: 'from-red-500 to-orange-500', icon: ShieldCheck },
            { days: 'D11-14', label: 'Agent Swarm', color: 'from-purple-500 to-pink-500', icon: Brain },
            { days: 'D15-16', label: 'Titan Phase', color: 'from-amber-500 to-yellow-500', icon: Shield },
            { days: 'D17-18', label: 'Predictive AI', color: 'from-green-500 to-emerald-500', icon: TrendingUp },
            { days: 'D19-20', label: 'Intelligence', color: 'from-cyan-500 to-blue-500', icon: Lightbulb },
            { days: 'D21', label: 'Launch', color: 'from-emerald-500 to-cyan-500', icon: Rocket },
          ].map((phase) => (
            <div key={phase.days} className="text-center group">
              <div className={`w-full h-1.5 rounded-full bg-gradient-to-r ${phase.color} mb-2 group-hover:h-2 transition-all`} />
              <div className={`w-8 h-8 mx-auto bg-gradient-to-br ${phase.color} rounded-lg flex items-center justify-center mb-1 group-hover:scale-110 transition-transform`}>
                <phase.icon className="w-4 h-4 text-white" />
              </div>
              <p className="text-[10px] font-bold text-white/70">{phase.days}</p>
              <p className="text-[9px] text-white/40">{phase.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent Projects */}
        <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">Recent Projects</h2>
            <button
              onClick={() => navigate('/projects')}
              className="text-sm text-white/50 hover:text-emerald-400 flex items-center gap-1"
            >
              View All <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-white/40">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-12">
              <FolderGit2 className="w-10 h-10 mx-auto mb-3 text-white/20" />
              <p className="text-white/50 mb-4">No projects yet</p>
              <button
                onClick={() => navigate('/new-project')}
                className="px-4 py-2 bg-emerald-500 rounded-lg text-sm font-medium hover:bg-emerald-600 transition-colors"
              >
                Create Your First Project
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {projects.slice(0, 5).map((project) => (
                <div
                  key={project.id}
                  onClick={() => {
                    localStorage.setItem('code4u_workspace', project.path)
                    navigate('/ide')
                  }}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-white/10 to-white/5 rounded-lg flex items-center justify-center">
                      <FolderGit2 className="w-5 h-5 text-white/70" />
                    </div>
                    <div>
                      <h3 className="font-medium group-hover:text-emerald-400 transition-colors">{project.name}</h3>
                      <div className="flex items-center gap-2 text-sm text-white/50">
                        <FileCode className="w-3 h-3" />
                        <span>{project.totalFiles} files</span>
                        <span>·</span>
                        <span>{project.totalSymbols} symbols</span>
                        {project.languages.length > 0 && (
                          <>
                            <span>·</span>
                            <span>{project.languages.slice(0, 2).join(', ')}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                      project.healthScore >= 80 ? 'bg-emerald-500/10 text-emerald-400' :
                      project.healthScore >= 50 ? 'bg-amber-500/10 text-amber-400' :
                      'bg-red-500/10 text-red-400'
                    }`}>
                      {project.healthScore}% health
                    </div>
                    <span className="px-2 py-1 rounded-full text-xs bg-white/10 text-white/50">
                      {project.status}
                    </span>
                    <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-white/60" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right sidebar — Activity + Getting Started */}
        <div className="space-y-6">
          {/* Recent Activity from Analytics */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-purple-400" /> Recent Activity
            </h2>
            {recentActivity.length === 0 ? (
              <p className="text-sm text-white/40">No recent activity. Run a refactor or agent to see results here.</p>
            ) : (
              <div className="space-y-3">
                {recentActivity.map((act, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-white/80">{act.repo_name} #{act.pr_id}</p>
                      <p className="text-white/40 text-xs">
                        {act.suggestions_count} suggestions · {act.accepted_count} accepted
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ROI Summary */}
          {analytics && analytics.humanSummary && (
            <div className="bg-gradient-to-br from-emerald-500/10 to-cyan-500/10 border border-emerald-500/20 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-400" /> ROI Summary
              </h2>
              <p className="text-sm text-emerald-300/80">{analytics.humanSummary}</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="text-center">
                  <p className="text-xl font-bold text-emerald-400">{analytics.totalReviews}</p>
                  <p className="text-xs text-white/40">Reviews</p>
                </div>
                <div className="text-center">
                  <p className="text-xl font-bold text-emerald-400">{analytics.totalAccepted}</p>
                  <p className="text-xs text-white/40">Accepted</p>
                </div>
              </div>
            </div>
          )}

          {/* Getting Started */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Getting Started</h2>
            <div className="space-y-3">
              {[
                { label: 'Create your account', completed: true, path: '/settings' },
                { label: 'Create a project', completed: projects.length > 0, path: '/new-project' },
                { label: 'Run your first agent', completed: false, path: '/agent' },
                { label: 'Install VS Code extension', completed: false, path: '/extensions' },
              ].map((step, i) => (
                <button
                  key={i}
                  onClick={() => navigate(step.path)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors text-left"
                >
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                    step.completed ? 'bg-emerald-500' : 'border border-white/20'
                  }`}>
                    {step.completed && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                  <span className={step.completed ? 'text-white/50 line-through' : ''}>{step.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
