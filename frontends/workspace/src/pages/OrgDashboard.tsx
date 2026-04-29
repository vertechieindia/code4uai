import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Globe,
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Download,
  Clock,
  FileText,
  Activity,
  BarChart3,
  Eye,
  ChevronUp,
  ChevronDown,
  Lightbulb,
  BookOpen,
  Users,
  GitBranch,
  Sparkles,
} from 'lucide-react'
import { useDarkMode } from '../App'

const getScoreColor = (score: number) => {
  if (score >= 80) return { bg: 'bg-emerald-500', text: 'text-emerald-400', gradient: 'from-emerald-500 to-green-400' }
  if (score >= 60) return { bg: 'bg-amber-500', text: 'text-amber-400', gradient: 'from-amber-500 to-yellow-400' }
  if (score >= 40) return { bg: 'bg-orange-500', text: 'text-orange-400', gradient: 'from-orange-500 to-red-400' }
  return { bg: 'bg-red-500', text: 'text-red-400', gradient: 'from-red-600 to-red-400' }
}

const getTreemapColor = (score: number) => {
  if (score >= 81) return 'bg-emerald-600'
  if (score >= 61) return 'bg-emerald-400'
  if (score >= 31) return 'bg-amber-500'
  return 'bg-red-600'
}

interface Project {
  id: string
  name: string
  language: string
  files: number
  securityScore: number
  criticalIssues: number
  highIssues: number
  mediumIssues: number
  lastScan: string
  status: 'secure' | 'at-risk' | 'critical'
  team: string
  dependencies: number
}

const mockProjects: Project[] = [
  { id: '1', name: 'api-gateway', language: 'TypeScript', files: 342, securityScore: 92, criticalIssues: 0, highIssues: 1, mediumIssues: 3, lastScan: '5 min ago', status: 'secure', team: 'Platform', dependencies: 156 },
  { id: '2', name: 'auth-service', language: 'Python', files: 128, securityScore: 78, criticalIssues: 1, highIssues: 3, mediumIssues: 5, lastScan: '12 min ago', status: 'at-risk', team: 'Identity', dependencies: 89 },
  { id: '3', name: 'payment-engine', language: 'Go', files: 256, securityScore: 45, criticalIssues: 3, highIssues: 8, mediumIssues: 12, lastScan: '1 hour ago', status: 'critical', team: 'Payments', dependencies: 67 },
  { id: '4', name: 'user-dashboard', language: 'React', files: 189, securityScore: 88, criticalIssues: 0, highIssues: 2, mediumIssues: 4, lastScan: '30 min ago', status: 'secure', team: 'Frontend', dependencies: 234 },
  { id: '5', name: 'ml-pipeline', language: 'Python', files: 412, securityScore: 62, criticalIssues: 2, highIssues: 5, mediumIssues: 9, lastScan: '2 hours ago', status: 'at-risk', team: 'Data', dependencies: 178 },
  { id: '6', name: 'notification-svc', language: 'Java', files: 98, securityScore: 95, criticalIssues: 0, highIssues: 0, mediumIssues: 2, lastScan: '8 min ago', status: 'secure', team: 'Platform', dependencies: 45 },
  { id: '7', name: 'data-warehouse', language: 'SQL', files: 567, securityScore: 33, criticalIssues: 5, highIssues: 12, mediumIssues: 20, lastScan: '3 hours ago', status: 'critical', team: 'Data', dependencies: 23 },
  { id: '8', name: 'mobile-app', language: 'Kotlin', files: 234, securityScore: 71, criticalIssues: 1, highIssues: 4, mediumIssues: 7, lastScan: '45 min ago', status: 'at-risk', team: 'Mobile', dependencies: 112 },
  { id: '9', name: 'infrastructure', language: 'Terraform', files: 156, securityScore: 84, criticalIssues: 0, highIssues: 2, mediumIssues: 6, lastScan: '20 min ago', status: 'secure', team: 'DevOps', dependencies: 34 },
  { id: '10', name: 'search-engine', language: 'Rust', files: 198, securityScore: 91, criticalIssues: 0, highIssues: 1, mediumIssues: 2, lastScan: '15 min ago', status: 'secure', team: 'Platform', dependencies: 56 },
  { id: '11', name: 'legacy-monolith', language: 'PHP', files: 1234, securityScore: 28, criticalIssues: 8, highIssues: 15, mediumIssues: 34, lastScan: '6 hours ago', status: 'critical', team: 'Legacy', dependencies: 289 },
  { id: '12', name: 'admin-portal', language: 'Vue', files: 167, securityScore: 82, criticalIssues: 0, highIssues: 3, mediumIssues: 5, lastScan: '25 min ago', status: 'secure', team: 'Frontend', dependencies: 145 },
]

const mockRecentAlerts = [
  { id: '1', project: 'payment-engine', message: 'Critical CVE detected in dependency', severity: 'critical', timestamp: '15 min ago' },
  { id: '2', project: 'legacy-monolith', message: 'SQL injection vulnerability found', severity: 'high', timestamp: '1 hour ago' },
  { id: '3', project: 'auth-service', message: 'Hardcoded secret detected', severity: 'medium', timestamp: '2 hours ago' },
  { id: '4', project: 'data-warehouse', message: 'Outdated dependency flagged', severity: 'high', timestamp: '3 hours ago' },
  { id: '5', project: 'ml-pipeline', message: 'SAST finding: XSS risk', severity: 'medium', timestamp: '4 hours ago' },
]

const mockHotspots = [
  { file: 'src/api/routes/auth.py', riskScore: 92, changes: 47, authors: 5, complexity: 35, riskLevel: 'critical' as const },
  { file: 'src/core/orchestrator.py', riskScore: 85, changes: 38, authors: 4, complexity: 42, riskLevel: 'critical' as const },
  { file: 'src/agents/heal_agent.py', riskScore: 68, changes: 32, authors: 3, complexity: 28, riskLevel: 'high' as const },
  { file: 'src/ui/Dashboard.tsx', riskScore: 54, changes: 28, authors: 6, complexity: 18, riskLevel: 'high' as const },
  { file: 'src/security/sentinel.py', riskScore: 45, changes: 25, authors: 3, complexity: 22, riskLevel: 'medium' as const },
  { file: 'src/validation/gauntlet.py', riskScore: 38, changes: 22, authors: 2, complexity: 32, riskLevel: 'medium' as const },
  { file: 'src/api/routes/models.py', riskScore: 30, changes: 20, authors: 4, complexity: 15, riskLevel: 'medium' as const },
  { file: 'src/core/config.py', riskScore: 18, changes: 18, authors: 5, complexity: 8, riskLevel: 'low' as const },
]

function treemapProjects(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => b.files - a.files)
}

const mockWisdomNuggets = [
  { id: '1', type: 'security_fix', language: 'Python', description: 'Fixed SQL injection via parameterized queries in auth module', project: 'a3f8...b2c1', tags: ['sql', 'injection'], usageCount: 12, confidence: 0.92, createdAt: '2 days ago' },
  { id: '2', type: 'performance_fix', language: 'TypeScript', description: 'Replaced synchronous file read with streaming for large datasets', project: 'e7d4...f1a9', tags: ['performance', 'streaming'], usageCount: 8, confidence: 0.87, createdAt: '5 days ago' },
  { id: '3', type: 'bug_fix', language: 'Go', description: 'Fixed race condition in concurrent map access with sync.RWMutex', project: '1b2c...d3e4', tags: ['concurrency', 'race-condition'], usageCount: 15, confidence: 0.95, createdAt: '1 week ago' },
  { id: '4', type: 'accessibility_fix', language: 'React', description: 'Added aria-labels to interactive elements and keyboard navigation', project: 'f5a6...7b8c', tags: ['accessibility', 'a11y'], usageCount: 6, confidence: 0.81, createdAt: '3 days ago' },
  { id: '5', type: 'security_fix', language: 'Java', description: 'Removed hardcoded credentials, migrated to vault-based secret management', project: '9d0e...1f2g', tags: ['credentials', 'secrets'], usageCount: 19, confidence: 0.96, createdAt: '1 day ago' },
  { id: '6', type: 'refactor', language: 'Python', description: 'Extracted common validation logic into shared middleware', project: 'h3i4...j5k6', tags: ['refactor', 'middleware'], usageCount: 4, confidence: 0.78, createdAt: '4 days ago' },
]

const mockDuplicates = [
  { function: 'validateEmail()', project: 'auth-service', similarTo: 'checkEmailFormat()', otherProject: 'user-dashboard', similarity: 0.89 },
  { function: 'hashPassword()', project: 'auth-service', similarTo: 'encryptPassword()', otherProject: 'admin-portal', similarity: 0.92 },
  { function: 'parseCSV()', project: 'data-warehouse', similarTo: 'readCSVFile()', otherProject: 'ml-pipeline', similarity: 0.85 },
  { function: 'formatDate()', project: 'user-dashboard', similarTo: 'dateToString()', otherProject: 'mobile-app', similarity: 0.78 },
]

const mockProjectWisdom = [
  { name: 'auth-service', contributed: 12, consumed: 8, wisdomScore: 92 },
  { name: 'api-gateway', contributed: 8, consumed: 15, wisdomScore: 85 },
  { name: 'payment-engine', contributed: 3, consumed: 12, wisdomScore: 68 },
  { name: 'ml-pipeline', contributed: 6, consumed: 4, wisdomScore: 74 },
  { name: 'user-dashboard', contributed: 5, consumed: 9, wisdomScore: 71 },
  { name: 'data-warehouse', contributed: 2, consumed: 7, wisdomScore: 55 },
]

export default function OrgDashboard() {
  const { darkMode } = useDarkMode()
  const [viewTab, setViewTab] = useState<'security' | 'intelligence'>('security')
  const [viewMode, setViewMode] = useState<'heatmap' | 'grid' | 'list'>('heatmap')
  const [sortColumn, setSortColumn] = useState<string>('securityScore')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(() => new Date())
  const [showSchedulePicker, setShowSchedulePicker] = useState(false)
  const [hoveredProject, setHoveredProject] = useState<string | null>(null)

  const treemapProjectsSorted = useMemo(() => treemapProjects(mockProjects), [])
  const totalFiles = useMemo(() => treemapProjectsSorted.reduce((s: number, p: Project) => s + p.files, 0), [treemapProjectsSorted])

  const totalCritical = mockProjects.reduce((sum, p) => sum + p.criticalIssues, 0)
  const avgScore = Math.round(mockProjects.reduce((sum, p) => sum + p.securityScore, 0) / mockProjects.length)
  const secureCount = mockProjects.filter(p => p.status === 'secure').length
  const complianceRate = Math.round((secureCount / mockProjects.length) * 100)

  const severityBreakdown = useMemo(() => {
    const critical = mockProjects.reduce((s, p) => s + p.criticalIssues, 0)
    const high = mockProjects.reduce((s, p) => s + p.highIssues, 0)
    const medium = mockProjects.reduce((s, p) => s + p.mediumIssues, 0)
    const low = mockProjects.filter(p => p.mediumIssues === 0 && p.highIssues === 0 && p.criticalIssues === 0).length
    const info = 0
    return { critical, high, medium, low, info, total: critical + high + medium + low + info || 1 }
  }, [])

  const conicGradient = useMemo(() => {
    const { critical, high, medium, low, info, total } = severityBreakdown
    let acc = 0
    const parts: string[] = []
    if (critical) { parts.push(`#ef4444 ${(acc / total) * 360}deg ${((acc += critical) / total) * 360}deg`); }
    if (high) { parts.push(`#f97316 ${(acc / total) * 360}deg ${((acc += high) / total) * 360}deg`); }
    if (medium) { parts.push(`#eab308 ${(acc / total) * 360}deg ${((acc += medium) / total) * 360}deg`); }
    if (low) { parts.push(`#22c55e ${(acc / total) * 360}deg ${((acc += low) / total) * 360}deg`); }
    if (info) { parts.push(`#3b82f6 ${(acc / total) * 360}deg 360deg`); }
    return parts.length ? `conic-gradient(${parts.join(', ')})` : 'conic-gradient(#334155 0deg 360deg)'
  }, [severityBreakdown])

  const sortedProjects = useMemo(() => {
    const sorted = [...mockProjects].sort((a, b) => {
      const aVal = (a as unknown as Record<string, unknown>)[sortColumn]
      const bVal = (b as unknown as Record<string, unknown>)[sortColumn]
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
      }
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return 0
    })
    return sorted
  }, [sortColumn, sortDirection])

  const topRiskyProjects = useMemo(() =>
    [...mockProjects].sort((a, b) => a.securityScore - b.securityScore).slice(0, 5),
  [])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setIsRefreshing(false)
      setLastUpdated(new Date())
    }, 1200)
  }

  const handleSort = (col: string) => {
    if (sortColumn === col) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(col)
      setSortDirection('asc')
    }
  }

  const handleExportReport = () => {
    const report = `# Organization Security Report
Generated: ${new Date().toISOString()}

## Executive Summary
- Total Projects: ${mockProjects.length}
- Average Security Score: ${avgScore}%
- Critical Vulnerabilities: ${totalCritical}
- Compliance Rate: ${complianceRate}%

## Projects
| Project | Language | Files | Score | Critical | Status |
|---------|----------|-------|-------|----------|--------|
${mockProjects.map(p => `| ${p.name} | ${p.language} | ${p.files} | ${p.securityScore}% | ${p.criticalIssues} | ${p.status} |`).join('\n')}
`
    const blob = new Blob([report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `org-security-report-${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const cardBase = darkMode
    ? 'bg-white/5 border border-white/10 backdrop-blur-sm'
    : 'bg-white/90 border border-slate-200/80 backdrop-blur-sm'
  const subText = darkMode ? 'text-white/50' : 'text-slate-500'

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Globe className="w-8 h-8 text-emerald-400" />
            Organization Security Posture
          </h1>
          <p className={`mt-1 ${subText}`}>Real-time security health across all projects</p>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <span className={`text-sm ${subText} flex items-center gap-1`}>
            <Clock className="w-4 h-4" />
            Last Updated: {lastUpdated.toLocaleTimeString()}
          </span>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleRefresh}
            disabled={isRefreshing}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
              darkMode ? 'bg-white/10 hover:bg-white/15 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
            } disabled:opacity-50`}
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </motion.button>
          <div className={`flex rounded-lg overflow-hidden border ${darkMode ? 'border-white/10' : 'border-slate-200'}`}>
            {(['heatmap', 'grid', 'list'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
                  viewMode === mode
                    ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white'
                    : darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className={`flex gap-1 p-1 rounded-lg ${darkMode ? 'bg-white/5' : 'bg-slate-100'}`}>
        <button
          onClick={() => setViewTab('security')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            viewTab === 'security'
              ? darkMode ? 'bg-white/10 text-white' : 'bg-white text-slate-900 shadow-sm'
              : darkMode ? 'text-white/50 hover:text-white' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Security Posture
        </button>
        <button
          onClick={() => setViewTab('intelligence')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
            viewTab === 'intelligence'
              ? darkMode ? 'bg-white/10 text-white' : 'bg-white text-slate-900 shadow-sm'
              : darkMode ? 'text-white/50 hover:text-white' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          Collective Intelligence
        </button>
      </div>

      {viewTab === 'security' && (
        <>
      {/* 2. Executive Summary Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Projects', value: mockProjects.length, icon: TrendingUp, gradient: 'from-emerald-500 to-cyan-500', iconColor: 'text-emerald-400' },
          { label: 'Avg Security Score', value: `${avgScore}%`, icon: BarChart3, gradient: getScoreColor(avgScore).gradient, valueColor: getScoreColor(avgScore).text, iconColor: getScoreColor(avgScore).text },
          { label: 'Critical Vulnerabilities', value: totalCritical, icon: AlertTriangle, gradient: 'from-red-500 to-orange-500', valueColor: 'text-red-400', iconColor: 'text-red-400' },
          { label: 'Compliance Rate', value: `${complianceRate}%`, icon: CheckCircle, gradient: 'from-emerald-500 to-green-500', iconColor: 'text-emerald-400' },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`${cardBase} rounded-xl p-5 relative overflow-hidden`}
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} opacity-5 rounded-xl`} />
            <div className="absolute top-0 right-0 w-20 h-20 rounded-full border-2 border-white/5 -translate-y-1/2 translate-x-1/2" />
            <div className="relative">
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className={`w-5 h-5 ${stat.iconColor || 'text-emerald-400'}`} />
                <span className={`text-sm font-semibold ${subText}`}>{stat.label}</span>
              </div>
              <p className={`text-2xl font-bold ${stat.valueColor || ''}`}>{stat.value}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* 3. Main content: Heatmap (70%) + Risk Panel (30%) */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        {/* Security Heatmap */}
        <motion.div
          layout
          className={`${cardBase} rounded-2xl p-6 min-h-[400px]`}
        >
          <h2 className="text-lg font-semibold mb-4">Security Heatmap</h2>
          {viewMode === 'heatmap' && (
            <div className="flex flex-wrap gap-2 min-h-[320px]">
              {treemapProjectsSorted.map(project => {
                const color = getTreemapColor(project.securityScore)
                const isHovered = hoveredProject === project.id
                const flexBasis = Math.max(15, (project.files / totalFiles) * 100)
                return (
                  <motion.div
                    key={project.id}
                    layout
                    className={`${color} rounded-lg p-3 flex flex-col justify-between cursor-pointer relative overflow-hidden min-w-[120px] transition-all ${
                      isHovered ? 'ring-2 ring-white/50 scale-[1.02] z-10' : 'hover:ring-2 hover:ring-white/30'
                    }`}
                    style={{ flex: `1 1 ${flexBasis}%` }}
                    onMouseEnter={() => setHoveredProject(project.id)}
                    onMouseLeave={() => setHoveredProject(null)}
                  >
                    <div className="flex items-start justify-between">
                      <span className="font-medium text-white text-sm truncate">{project.name}</span>
                      {project.criticalIssues > 0 && (
                        <span className="w-2 h-2 rounded-full bg-red-300 flex-shrink-0" />
                      )}
                    </div>
                    <div className="text-xs text-white/90">
                      <span className="font-semibold">{project.securityScore}</span> · {project.files} files
                    </div>
                    {isHovered && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 bg-black/60 rounded-lg flex flex-col justify-center p-3"
                      >
                        <p className="text-white font-medium text-sm">{project.name}</p>
                        <p className="text-white/80 text-xs">Score: {project.securityScore}% · Files: {project.files}</p>
                        <p className="text-white/70 text-xs">Critical: {project.criticalIssues} · High: {project.highIssues}</p>
                        <p className="text-white/60 text-xs">{project.team}</p>
                      </motion.div>
                    )}
                  </motion.div>
                )
              })}
            </div>
          )}
          {viewMode === 'grid' && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {mockProjects.map(p => (
                <motion.div
                  key={p.id}
                  layout
                  className={`${getTreemapColor(p.securityScore)} rounded-xl p-4 cursor-pointer hover:ring-2 hover:ring-white/30 transition-all`}
                  onClick={() => setSelectedProject(p.id)}
                >
                  <p className="font-medium text-white text-sm">{p.name}</p>
                  <p className="text-white/90 text-xs mt-1">{p.securityScore}% · {p.files} files</p>
                </motion.div>
              ))}
            </div>
          )}
          {viewMode === 'list' && (
            <div className="space-y-2">
              {mockProjects.map(p => (
                <motion.div
                  key={p.id}
                  layout
                  className={`flex items-center justify-between p-3 rounded-lg ${darkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-slate-50 hover:bg-slate-100'} transition-colors cursor-pointer`}
                  onClick={() => setSelectedProject(p.id)}
                >
                  <span className="font-medium">{p.name}</span>
                  <div className="flex items-center gap-4">
                    <span className={getScoreColor(p.securityScore).text}>{p.securityScore}%</span>
                    <span className={subText}>{p.files} files</span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>

        {/* 4. Risk Distribution Panel */}
        <div className="space-y-6">
          <motion.div
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            className={`${cardBase} rounded-2xl p-6`}
          >
            <h2 className="text-lg font-semibold mb-4">Severity Breakdown</h2>
            <div className="flex items-center gap-6">
              <div
                className="w-28 h-28 rounded-full flex-shrink-0"
                style={{ background: conicGradient }}
              />
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-500" /> Critical: {severityBreakdown.critical}</div>
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-orange-500" /> High: {severityBreakdown.high}</div>
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-500" /> Medium: {severityBreakdown.medium}</div>
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Low: {severityBreakdown.low}</div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className={`${cardBase} rounded-2xl p-6`}
          >
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              Top 5 Risky Projects
            </h2>
            <div className="space-y-3">
              {topRiskyProjects.map(p => (
                <div key={p.id} className="flex items-center gap-3">
                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{p.name}</p>
                    <div className="mt-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${getScoreColor(p.securityScore).bg}`}
                        style={{ width: `${p.securityScore}%` }}
                      />
                    </div>
                  </div>
                  <span className={`text-sm font-semibold ${getScoreColor(p.securityScore).text}`}>{p.securityScore}</span>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className={`${cardBase} rounded-2xl p-6`}
          >
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              Recent Alerts
            </h2>
            <div className="space-y-3">
              {mockRecentAlerts.map(alert => (
                <div key={alert.id} className={`p-3 rounded-lg ${darkMode ? 'bg-black/20' : 'bg-slate-50'}`}>
                  <p className="text-sm font-medium truncate">{alert.project}</p>
                  <p className="text-xs text-white/60 mt-0.5">{alert.message}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                      alert.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                      'bg-amber-500/20 text-amber-400'
                    }`}>{alert.severity}</span>
                    <span className="text-[10px] text-white/40">{alert.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* 5. Projects Table */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className={`${cardBase} rounded-2xl overflow-hidden`}
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className={`border-b ${darkMode ? 'border-white/10' : 'border-slate-200'}`}>
                {[
                  { key: 'name', label: 'Project Name' },
                  { key: 'language', label: 'Language' },
                  { key: 'files', label: 'Files' },
                  { key: 'securityScore', label: 'Security Score' },
                  { key: 'criticalIssues', label: 'Critical Issues' },
                  { key: 'lastScan', label: 'Last Scan' },
                  { key: 'status', label: 'Status' },
                  { key: 'actions', label: 'Actions' },
                ].map(({ key, label }) => (
                  <th
                    key={key}
                    className={`px-4 py-3 text-left text-sm font-semibold ${subText} ${key !== 'actions' ? 'cursor-pointer hover:text-white' : ''}`}
                    onClick={() => key !== 'actions' && handleSort(key)}
                  >
                    <div className="flex items-center gap-1">
                      {label}
                      {key !== 'actions' && sortColumn === key && (
                        sortDirection === 'asc' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map(project => (
                <tr
                  key={project.id}
                  className={`border-b transition-colors ${
                    selectedProject === project.id
                      ? darkMode ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-200'
                      : darkMode ? 'border-white/5 hover:bg-white/5' : 'border-slate-100 hover:bg-slate-50'
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-white/40" />
                      <span className="font-medium">{project.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${darkMode ? 'bg-white/10' : 'bg-slate-100'}`}>
                      {project.language}
                    </span>
                  </td>
                  <td className="px-4 py-3">{project.files}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 w-24">
                      <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${getScoreColor(project.securityScore).bg}`}
                          style={{ width: `${project.securityScore}%` }}
                        />
                      </div>
                      <span className={`text-sm font-medium ${getScoreColor(project.securityScore).text}`}>{project.securityScore}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={project.criticalIssues > 0 ? 'text-red-400 font-semibold' : subText}>
                      {project.criticalIssues}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-sm ${subText}`}>{project.lastScan}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      project.status === 'secure' ? 'bg-emerald-500/20 text-emerald-400' :
                      project.status === 'at-risk' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {project.status === 'secure' ? 'Secure' : project.status === 'at-risk' ? 'At Risk' : 'Critical'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => setSelectedProject(project.id)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-emerald-400 hover:from-emerald-500/30 hover:to-cyan-500/30 transition-colors"
                    >
                      <Eye className="w-4 h-4" />
                      View Details
                    </motion.button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Churn Risk Hotspots */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className={`rounded-2xl p-6 ${darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'}`}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-orange-400" />
            <h2 className="text-lg font-semibold">Churn Risk Hotspots</h2>
          </div>
          <span className={`text-xs ${darkMode ? 'text-white/40' : 'text-slate-400'}`}>
            Based on last 90 days of git history
          </span>
        </div>

        <div className="space-y-2">
          {mockHotspots.map((hotspot, i) => (
            <div
              key={hotspot.file}
              className={`flex items-center justify-between p-3 rounded-lg ${
                darkMode ? 'bg-black/30 border border-white/5' : 'bg-slate-50 border border-slate-100'
              }`}
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <span
                  className={`w-6 h-6 flex items-center justify-center rounded text-xs font-bold ${
                    hotspot.riskLevel === 'critical'
                      ? 'bg-red-500/20 text-red-400'
                      : hotspot.riskLevel === 'high'
                        ? 'bg-orange-500/20 text-orange-400'
                        : hotspot.riskLevel === 'medium'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-emerald-500/20 text-emerald-400'
                  }`}
                >
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-mono truncate">{hotspot.file}</p>
                  <p className={`text-[10px] ${darkMode ? 'text-white/40' : 'text-slate-400'}`}>
                    {hotspot.changes} changes · {hotspot.authors} authors · Complexity: {hotspot.complexity}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-24">
                  <div className={`h-1.5 rounded-full ${darkMode ? 'bg-white/10' : 'bg-slate-200'}`}>
                    <div
                      className={`h-full rounded-full ${
                        hotspot.riskLevel === 'critical'
                          ? 'bg-red-500'
                          : hotspot.riskLevel === 'high'
                            ? 'bg-orange-500'
                            : hotspot.riskLevel === 'medium'
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                      }`}
                      style={{ width: `${hotspot.riskScore}%` }}
                    />
                  </div>
                </div>
                <span
                  className={`text-sm font-bold w-12 text-right ${
                    hotspot.riskLevel === 'critical'
                      ? 'text-red-400'
                      : hotspot.riskLevel === 'high'
                        ? 'text-orange-400'
                        : hotspot.riskLevel === 'medium'
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                  }`}
                >
                  {hotspot.riskScore}
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium uppercase ${
                    hotspot.riskLevel === 'critical'
                      ? 'bg-red-500/20 text-red-400'
                      : hotspot.riskLevel === 'high'
                        ? 'bg-orange-500/20 text-orange-400'
                        : hotspot.riskLevel === 'medium'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-emerald-500/20 text-emerald-400'
                  }`}
                >
                  {hotspot.riskLevel}
                </span>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

        </>
      )}

      {viewTab === 'intelligence' && (
        <div className="space-y-6">
          {/* Intelligence Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: 'Wisdom Nuggets', value: '47', icon: Lightbulb, color: 'text-amber-400', bg: darkMode ? 'bg-amber-500/10 border-amber-500/20' : 'bg-amber-50 border-amber-200' },
              { label: 'Shared Fixes', value: '156', icon: GitBranch, color: 'text-cyan-400', bg: darkMode ? 'bg-cyan-500/10 border-cyan-500/20' : 'bg-cyan-50 border-cyan-200' },
              { label: 'Duplicates Found', value: mockDuplicates.length.toString(), icon: BookOpen, color: 'text-purple-400', bg: darkMode ? 'bg-purple-500/10 border-purple-500/20' : 'bg-purple-50 border-purple-200' },
              { label: 'Active Contributors', value: '6', icon: Users, color: 'text-emerald-400', bg: darkMode ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-200' },
            ].map((stat) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-4 rounded-xl border ${stat.bg}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className={`text-xs ${darkMode ? 'text-white/50' : 'text-slate-500'}`}>{stat.label}</div>
              </motion.div>
            ))}
          </div>

          {/* Two column layout: Recent Nuggets + Duplicates */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recently Shared Fixes */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`rounded-2xl p-6 ${darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'}`}
            >
              <div className="flex items-center gap-3 mb-4">
                <Lightbulb className="w-5 h-5 text-amber-400" />
                <h2 className="text-lg font-semibold">Recently Shared Fixes</h2>
              </div>
              <div className="space-y-3">
                {mockWisdomNuggets.map((nugget) => (
                  <div key={nugget.id} className={`p-3 rounded-lg ${darkMode ? 'bg-black/30 border border-white/5' : 'bg-slate-50 border border-slate-100'}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                            nugget.type === 'security_fix' ? 'bg-red-500/20 text-red-400' :
                            nugget.type === 'performance_fix' ? 'bg-blue-500/20 text-blue-400' :
                            nugget.type === 'bug_fix' ? 'bg-amber-500/20 text-amber-400' :
                            nugget.type === 'accessibility_fix' ? 'bg-cyan-500/20 text-cyan-400' :
                            'bg-purple-500/20 text-purple-400'
                          }`}>
                            {nugget.type.replace('_', ' ')}
                          </span>
                          <span className={`text-[10px] ${darkMode ? 'text-white/30' : 'text-slate-400'}`}>{nugget.language}</span>
                        </div>
                        <p className="text-sm truncate">{nugget.description}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className={`text-[10px] ${darkMode ? 'text-white/30' : 'text-slate-400'}`}>
                            Project: {nugget.project}
                          </span>
                          <span className={`text-[10px] ${darkMode ? 'text-white/30' : 'text-slate-400'}`}>
                            {nugget.createdAt}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-bold text-emerald-400">{nugget.usageCount}x</div>
                        <div className={`text-[10px] ${darkMode ? 'text-white/30' : 'text-slate-400'}`}>reused</div>
                      </div>
                    </div>
                    <div className="flex gap-1 mt-2">
                      {nugget.tags.map(tag => (
                        <span key={tag} className={`text-[10px] px-1.5 py-0.5 rounded ${darkMode ? 'bg-white/5 text-white/40' : 'bg-slate-100 text-slate-500'}`}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Code Reuse Opportunities */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`rounded-2xl p-6 ${darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'}`}
            >
              <div className="flex items-center gap-3 mb-4">
                <BookOpen className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold">Code Reuse Opportunities</h2>
              </div>
              <p className={`text-xs mb-4 ${darkMode ? 'text-white/40' : 'text-slate-500'}`}>
                Functions with similar semantics found across different projects
              </p>
              <div className="space-y-3">
                {mockDuplicates.map((dup, i) => (
                  <div key={i} className={`p-3 rounded-lg ${darkMode ? 'bg-black/30 border border-white/5' : 'bg-slate-50 border border-slate-100'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-sm font-mono font-medium">{dup.function}</span>
                        <span className={`text-xs ml-2 ${darkMode ? 'text-white/30' : 'text-slate-400'}`}>in {dup.project}</span>
                      </div>
                      <span className={`text-sm font-bold ${dup.similarity >= 0.9 ? 'text-red-400' : dup.similarity >= 0.8 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(dup.similarity * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-3 h-3 text-white/30" />
                      <span className={`text-xs ${darkMode ? 'text-white/50' : 'text-slate-500'}`}>
                        Similar to <span className="font-mono">{dup.similarTo}</span> in <span className="font-medium">{dup.otherProject}</span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          {/* Project Wisdom Scores */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className={`rounded-2xl p-6 ${darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'}`}
          >
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-semibold">Project Wisdom Scores</h2>
              <span className={`text-xs ${darkMode ? 'text-white/40' : 'text-slate-400'}`}>
                How much each project contributes to and uses the shared knowledge
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {mockProjectWisdom.map((proj) => (
                <div key={proj.name} className={`p-4 rounded-xl ${darkMode ? 'bg-black/30 border border-white/5' : 'bg-slate-50 border border-slate-100'}`}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-sm">{proj.name}</span>
                    <span className={`text-lg font-bold ${
                      proj.wisdomScore >= 80 ? 'text-emerald-400' :
                      proj.wisdomScore >= 60 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {proj.wisdomScore}
                    </span>
                  </div>
                  <div className={`h-1.5 rounded-full mb-2 ${darkMode ? 'bg-white/10' : 'bg-slate-200'}`}>
                    <div
                      className={`h-full rounded-full ${
                        proj.wisdomScore >= 80 ? 'bg-emerald-500' :
                        proj.wisdomScore >= 60 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${proj.wisdomScore}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className={darkMode ? 'text-white/40' : 'text-slate-400'}>
                      Contributed: <span className="text-emerald-400 font-medium">{proj.contributed}</span>
                    </span>
                    <span className={darkMode ? 'text-white/40' : 'text-slate-400'}>
                      Consumed: <span className="text-cyan-400 font-medium">{proj.consumed}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      )}

      {/* 6. Bottom Bar */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className={`flex flex-wrap items-center justify-between gap-4 py-4 px-6 ${cardBase} rounded-xl`}
      >
        <div className="flex items-center gap-4 flex-wrap">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleExportReport}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
          >
            <Download className="w-4 h-4" />
            Export Organization Report
          </motion.button>
          <div className="relative">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setShowSchedulePicker(!showSchedulePicker)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
                darkMode ? 'bg-white/10 hover:bg-white/15' : 'bg-slate-100 hover:bg-slate-200'
              }`}
            >
              <Clock className="w-4 h-4" />
              Schedule Scan
            </motion.button>
            <AnimatePresence>
              {showSchedulePicker && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowSchedulePicker(false)} />
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className={`absolute left-0 top-full mt-2 z-50 w-64 rounded-xl shadow-xl border overflow-hidden ${
                      darkMode ? 'bg-[#0d1117] border-white/10' : 'bg-white border-slate-200'
                    }`}
                  >
                    <div className="p-4 space-y-2">
                      <p className="text-sm font-medium">Schedule recurring scan</p>
                      {['Daily', 'Weekly', 'Monthly'].map(opt => (
                        <button
                          key={opt}
                          onClick={() => setShowSchedulePicker(false)}
                          className={`w-full px-3 py-2 rounded-lg text-left text-sm ${darkMode ? 'hover:bg-white/10' : 'hover:bg-slate-50'}`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-sm text-white/60">NVD Watch: Active</span>
        </div>
      </motion.div>
    </div>
  )
}
