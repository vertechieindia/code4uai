import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield,
  Cpu,
  Layers,
  Monitor,
  Gauge,
  Heart,
  CheckCircle2,
  XCircle,
  Loader2,
  Download,
  AlertTriangle,
  Clock,
  Activity,
  Zap,
  Target,
  ShieldAlert,
  Scale,
  BookOpen,
  FileSearch,
  Eye,
  Ban,
} from 'lucide-react'

const GUARDIAN_STORAGE_KEY = 'guardian_gauntlet_status'
const GUARDIAN_TIMESTAMP_KEY = 'guardian_gauntlet_timestamp'

export type GauntletStatus = 'idle' | 'running' | 'passed' | 'failed' | 'quarantine'

export interface GauntletStage {
  id: number
  name: string
  description: string
  icon: typeof Cpu
  status: 'pending' | 'running' | 'passed' | 'failed' | 'healing'
  failures?: number
  duration?: number
}

const STAGE_CONFIG = [
  { id: 1, name: 'Core Tests', description: 'Unit, Smoke, Sanity', icon: Cpu },
  { id: 2, name: 'Functional Tests', description: 'Integration, Black/White/Grey Box', icon: Layers },
  { id: 3, name: 'System Tests', description: 'Regression, Acceptance, UI Automation', icon: Monitor },
  { id: 4, name: 'Non-Functional', description: 'Performance, A11y, i18n, Compatibility', icon: Gauge },
  { id: 5, name: 'Security Fortress', description: 'SAST, DAST, SCA, Pentest', icon: Shield },
]

const AGENT_COLORS: Record<string, string> = {
  Accessibility: 'text-cyan-400',
  Localization: 'text-amber-400',
  Compatibility: 'text-blue-400',
  Performance: 'text-purple-400',
  ThreatModel: 'text-red-400',
  Pentest: 'text-orange-400',
  Fuzz: 'text-pink-400',
  Audit: 'text-emerald-400',
  Chaos: 'text-rose-400',
  RedTeam: 'text-violet-400',
  Adversarial: 'text-yellow-400',
}

interface AgentLog {
  id: string
  timestamp: string
  agent: string
  message: string
}

const initialStages: GauntletStage[] = STAGE_CONFIG.map((c) => ({
  ...c,
  status: 'pending' as const,
}))

const mockSecurityBreakdown = {
  sast: { count: 12, critical: 0, high: 2, medium: 5, low: 5 },
  dast: { count: 3 },
  secretScan: 'pass' as const,
  dependencyAudit: 2,
}

function formatTime(ms: number) {
  return `${(ms / 1000).toFixed(1)}s`
}

function getScoreColor(score: number) {
  if (score <= 40) return 'stroke-red-500'
  if (score <= 70) return 'stroke-amber-500'
  return 'stroke-emerald-500'
}

function getScoreBgColor(score: number) {
  if (score <= 40) return 'text-red-400'
  if (score <= 70) return 'text-amber-400'
  return 'text-emerald-400'
}

export default function GuardianPage() {
  const [gauntletStages, setGauntletStages] = useState<GauntletStage[]>(initialStages)
  const [securityScore, setSecurityScore] = useState(72)
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>(() => {
    const base = [
      { id: '1', timestamp: '14:32:01', agent: 'Audit', message: 'Guardian initialized. Ready for gauntlet run.' },
      { id: '2', timestamp: '14:32:02', agent: 'ThreatModel', message: 'Threat model baseline loaded.' },
      { id: '3', timestamp: '14:32:03', agent: 'Performance', message: 'Performance baseline established.' },
    ]
    return base
  })
  const [currentCycle, setCurrentCycle] = useState(1)
  const [gauntletStatus, setGauntletStatus] = useState<GauntletStatus>('idle')
  const [isScanning, setIsScanning] = useState(false)
  const [lastScanTime, setLastScanTime] = useState<string | null>(null)
  const [isQuarantined] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const [cpuUsage, setCpuUsage] = useState(42)
  const [memoryUsage, setMemoryUsage] = useState(2.8)
  const [memoryTotal] = useState(8.0)
  const [activeAgents, setActiveAgents] = useState(5)
  const [maxAgents] = useState(8)
  const [throttleLimit, setThrottleLimit] = useState(8)

  const [chaosEnabled, setChaosEnabled] = useState(false)
  const [chaosIntensity, setChaosIntensity] = useState(30)
  const [chaosEvents, setChaosEvents] = useState<Array<{
    id: string
    type: string
    target: string
    recovered: boolean
    recoveryMs: number
    timestamp: string
  }>>([
    { id: 'c1', type: 'latency_injection', target: 'stage_core', recovered: true, recoveryMs: 1200, timestamp: '14:45:12' },
    { id: 'c2', type: 'process_kill', target: 'worker_2', recovered: true, recoveryMs: 340, timestamp: '14:45:18' },
    { id: 'c3', type: 'network_partition', target: 'llm_provider', recovered: true, recoveryMs: 2100, timestamp: '14:45:25' },
    { id: 'c4', type: 'stage_corruption', target: 'stage_functional', recovered: true, recoveryMs: 890, timestamp: '14:45:31' },
    { id: 'c5', type: 'memory_pressure', target: 'system', recovered: true, recoveryMs: 150, timestamp: '14:45:38' },
    { id: 'c6', type: 'latency_injection', target: 'stage_security', recovered: false, recoveryMs: 5000, timestamp: '14:45:44' },
  ])
  const [resilienceScore, setResilienceScore] = useState(83)
  const [redTeamFindings, setRedTeamFindings] = useState(0)
  const [adversarialScore, setAdversarialScore] = useState(100)
  const [guardianTab, setGuardianTab] = useState<'gauntlet' | 'governance'>('gauntlet')

  const workerProcesses = [
    { pid: 42891, name: 'ChiefArchitect', status: 'running' as const, cpu: 18.2, memory: 456, uptime: '12m 34s' },
    { pid: 42892, name: 'HealAgent', status: 'running' as const, cpu: 12.5, memory: 312, uptime: '8m 12s' },
    { pid: 42893, name: 'PentestAgent', status: 'idle' as const, cpu: 0.3, memory: 128, uptime: '45m 01s' },
    { pid: 42894, name: 'AccessibilityAgent', status: 'running' as const, cpu: 8.7, memory: 234, uptime: '3m 56s' },
    { pid: 42895, name: 'PerformanceAgent', status: 'idle' as const, cpu: 0.1, memory: 96, uptime: '1h 12m' },
    { pid: 42896, name: 'FuzzAgent', status: 'running' as const, cpu: 22.1, memory: 567, uptime: '6m 28s' },
  ]

  useEffect(() => {
    const interval = setInterval(() => {
      setCpuUsage(prev => Math.max(5, Math.min(95, prev + (Math.random() - 0.5) * 15)))
      setMemoryUsage(prev => Math.max(0.5, Math.min(7.5, prev + (Math.random() - 0.5) * 0.8)))
      setActiveAgents(prev => Math.max(1, Math.min(throttleLimit, prev + Math.round((Math.random() - 0.5) * 2))))
    }, 3000)
    return () => clearInterval(interval)
  }, [throttleLimit])

  const addLog = (agent: string, message: string) => {
    const now = new Date()
    const ts = now.toTimeString().slice(0, 8)
    setAgentLogs((prev) => {
      const next = [...prev, { id: String(Date.now()), timestamp: ts, agent, message }]
      return next.slice(-200)
    })
  }

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [agentLogs])

  const handleRunGauntlet = () => {
    if (gauntletStatus === 'running') return
    setGauntletStatus('running')
    setCurrentCycle(1)
    setGauntletStages(initialStages)
    addLog('Audit', 'Gauntlet run started. Cycle 1/10.')
    localStorage.setItem(GUARDIAN_STORAGE_KEY, 'running')
    localStorage.removeItem(GUARDIAN_TIMESTAMP_KEY)

    const runStage = (index: number, isRetry: boolean) => {
      if (index >= 5) {
        setGauntletStatus('passed')
        localStorage.setItem(GUARDIAN_STORAGE_KEY, 'passed')
        localStorage.setItem(GUARDIAN_TIMESTAMP_KEY, new Date().toISOString())
        addLog('Audit', 'All stages passed. Quality gate OPEN.')
        return
      }

      const stage = STAGE_CONFIG[index]
      setGauntletStages((prev) =>
        prev.map((s) => (s.id === stage.id ? { ...s, status: 'running' as const } : s))
      )
      addLog(stage.name, `Stage ${stage.id}: ${stage.name} — running...`)

      const shouldFail = !isRetry && index === 3
      const delay = 800 + Math.random() * 400

      setTimeout(() => {
        if (shouldFail) {
          setGauntletStages((prev) =>
            prev.map((s) =>
              s.id === stage.id
                ? { ...s, status: 'failed' as const, failures: 2 }
                : s
            )
          )
          addLog(stage.name, `Stage ${stage.id} FAILED — 2 failures. Heal Agent invoked.`)
          setGauntletStatus('running')
          localStorage.setItem(GUARDIAN_STORAGE_KEY, 'failed')

          setTimeout(() => {
            setGauntletStages((prev) =>
              prev.map((s) =>
                s.id === stage.id ? { ...s, status: 'healing' as const } : s
              )
            )
            addLog('Audit', 'Heal Agent fixing...')
          }, 300)

          setTimeout(() => {
            setCurrentCycle(2)
            setGauntletStages(initialStages)
            addLog('Audit', 'Healing complete. Restarting gauntlet — Cycle 2/10.')
            runStage(0, true)
          }, 1500)
        } else {
          const duration = Math.round(delay + 200)
          setGauntletStages((prev) =>
            prev.map((s) =>
              s.id === stage.id
                ? { ...s, status: 'passed' as const, duration }
                : s
            )
          )
          addLog(stage.name, `Stage ${stage.id} passed in ${formatTime(duration)}.`)
          runStage(index + 1, isRetry)
        }
      }, delay)
    }

    runStage(0, false)
  }

  const handleSecurityScan = () => {
    if (isScanning) return
    setIsScanning(true)
    addLog('Audit', 'Full Security Scan started...')
    setTimeout(() => {
      const newScore = Math.min(100, securityScore + Math.floor(Math.random() * 15))
      setSecurityScore(newScore)
      setLastScanTime(new Date().toLocaleTimeString())
      addLog('Audit', `Security scan complete. Score: ${newScore}/100`)
      setIsScanning(false)
    }, 2500)
  }

  const handleExportReport = () => {
    const report = `# Titan Audit Report
Generated: ${new Date().toISOString()}

## Gauntlet Status
- Status: ${gauntletStatus}
- Cycle: ${currentCycle}/10
- Last Run: ${lastScanTime || 'N/A'}

## Security Posture
- Security Score: ${securityScore}/100
- SAST Findings: ${mockSecurityBreakdown.sast.count}
- DAST Results: ${mockSecurityBreakdown.dast.count}
- Secret Scan: ${mockSecurityBreakdown.secretScan}
- Vulnerable Dependencies: ${mockSecurityBreakdown.dependencyAudit}

## Stages
${gauntletStages.map((s) => `- ${s.name}: ${s.status}`).join('\n')}
`
    const blob = new Blob([report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `titan-audit-${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    addLog('Audit', 'Titan Audit Report exported.')
  }

  const mockLicenseMatrix = {
    categories: ['permissive', 'weak_copyleft', 'strong_copyleft', 'proprietary'],
    matrix: {
      permissive: { permissive: true, weak_copyleft: true, strong_copyleft: true, proprietary: true },
      weak_copyleft: { permissive: true, weak_copyleft: true, strong_copyleft: true, proprietary: false },
      strong_copyleft: { permissive: false, weak_copyleft: false, strong_copyleft: true, proprietary: false },
      proprietary: { permissive: true, weak_copyleft: false, strong_copyleft: false, proprietary: false },
    } as Record<string, Record<string, boolean>>,
  }

  const mockProjectLicense = {
    licenseId: 'MIT',
    spdxId: 'MIT',
    category: 'permissive',
    copyleft: false,
    source: 'LICENSE',
    confidence: 0.95,
  }

  const mockViolations = [
    { id: 'v1', severity: 'critical', source: 'GPL-3.0', target: 'MIT', file: 'utils/parser.py', description: 'GPL copyleft code in permissive project', blocked: true, timestamp: '2 hours ago' },
    { id: 'v2', severity: 'high', source: 'AGPL-3.0', target: 'Proprietary', file: 'lib/auth.js', description: 'AGPL code in proprietary codebase', blocked: true, timestamp: '5 hours ago' },
  ]

  const mockProvenanceRecords = [
    { id: 'p1', file: 'src/auth/validate.py', change: 'Fixed SQL injection via parameterized queries', source: 'wisdom_nugget', nuggetProject: 'a3f8...b2c1', license: 'MIT', verified: true, applied: true, timestamp: '1 hour ago' },
    { id: 'p2', file: 'src/api/middleware.ts', change: 'Added rate limiting middleware', source: 'ai_generation', nuggetProject: null, license: null, verified: false, applied: true, timestamp: '3 hours ago' },
    { id: 'p3', file: 'src/utils/crypto.py', change: 'Replaced MD5 with bcrypt for password hashing', source: 'wisdom_nugget', nuggetProject: 'e7d4...f1a9', license: 'Apache-2.0', verified: true, applied: true, timestamp: '5 hours ago' },
    { id: 'p4', file: 'src/models/user.go', change: 'Added input validation for email fields', source: 'wisdom_nugget', nuggetProject: '1b2c...d3e4', license: 'MIT', verified: true, applied: false, timestamp: '6 hours ago' },
  ]

  const mockToxicMatches = [
    { id: 't1', category: 'ethical', severity: 'high', pattern: 'unauthorized_scraping_headers', file: 'scraper/agent.py', line: 42, description: 'Unauthorized impersonation of Googlebot', blocked: true },
    { id: 't2', category: 'bias', severity: 'critical', pattern: 'biased_threshold_race', file: 'ml/classifier.py', line: 118, description: 'Race-based conditional logic detected', blocked: true },
    { id: 't3', category: 'malware', severity: 'critical', pattern: 'crypto_mining_stealth', file: 'worker/bg.js', line: 7, description: 'Cryptocurrency mining code detected', blocked: true },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Shield className="w-8 h-8 text-emerald-400" />
            Guardian — Mission Control
          </h1>
          <p className="text-white/50 mt-1">
            Zero-Defect Fortress • Recursive Quality Gauntlet
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunGauntlet}
            disabled={gauntletStatus === 'running'}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white hover:shadow-lg hover:shadow-emerald-500/25 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {gauntletStatus === 'running' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Shield className="w-4 h-4" />
            )}
            Run Gauntlet
          </button>
          <button
            onClick={handleSecurityScan}
            disabled={isScanning}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-red-500 to-orange-500 rounded-lg font-semibold text-white hover:shadow-lg hover:shadow-red-500/25 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isScanning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <AlertTriangle className="w-4 h-4" />
            )}
            Full Security Scan
          </button>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-1 p-1 rounded-lg bg-white/5">
        <button
          onClick={() => setGuardianTab('gauntlet')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            guardianTab === 'gauntlet'
              ? 'bg-white/10 text-white'
              : 'text-white/50 hover:text-white'
          }`}
        >
          Quality Gauntlet
        </button>
        <button
          onClick={() => setGuardianTab('governance')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
            guardianTab === 'governance'
              ? 'bg-white/10 text-white'
              : 'text-white/50 hover:text-white'
          }`}
        >
          <Scale className="w-4 h-4" />
          Governance & Ethics
        </button>
      </div>

      {guardianTab === 'gauntlet' && (
        <>
      {/* Main Grid: Gauntlet (60%) + Security Gauge (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
        {/* Live Gauntlet Tracker */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">Live Gauntlet Tracker</h2>
            <span className="text-sm font-mono text-white/50 bg-black/30 px-3 py-1 rounded-lg">
              Cycle {currentCycle}/10
            </span>
          </div>

          <div className="relative">
            {gauntletStages.map((stage, idx) => {
              const Icon = stage.icon
              const isLast = idx === gauntletStages.length - 1
              const lineColor =
                stage.status === 'passed'
                  ? 'bg-emerald-500'
                  : stage.status === 'running' || stage.status === 'healing'
                    ? 'bg-red-500 animate-pulse'
                    : 'bg-white/10'

              return (
                <div key={stage.id} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <motion.div
                      layout
                      className={`w-14 h-14 rounded-xl flex items-center justify-center border ${
                        stage.status === 'passed'
                          ? 'bg-emerald-500/20 border-emerald-500/50'
                          : stage.status === 'failed'
                            ? 'bg-red-500/20 border-red-500/50'
                            : stage.status === 'running' || stage.status === 'healing'
                              ? 'bg-red-500/20 border-red-500/50 animate-pulse'
                              : 'bg-white/5 border-white/10'
                      }`}
                    >
                      {stage.status === 'healing' ? (
                        <Heart className="w-6 h-6 text-red-400 animate-pulse" />
                      ) : stage.status === 'passed' ? (
                        <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                      ) : stage.status === 'failed' ? (
                        <XCircle className="w-6 h-6 text-red-400" />
                      ) : stage.status === 'running' ? (
                        <Loader2 className="w-6 h-6 text-red-400 animate-spin" />
                      ) : (
                        <Icon className="w-6 h-6 text-white/40" />
                      )}
                    </motion.div>
                    {!isLast && (
                      <div
                        className={`w-0.5 flex-1 min-h-[24px] mt-2 rounded-full ${lineColor}`}
                      />
                    )}
                  </div>
                  <div className="flex-1 pb-6">
                    <motion.div
                      layout
                      className={`p-4 rounded-xl border transition-all ${
                        stage.status === 'passed'
                          ? 'bg-emerald-500/5 border-emerald-500/20'
                          : stage.status === 'failed'
                            ? 'bg-red-500/5 border-red-500/20'
                            : stage.status === 'running' || stage.status === 'healing'
                              ? 'bg-red-500/10 border-red-500/30'
                              : 'bg-white/5 border-white/10'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-white/40">
                            Stage {stage.id}
                          </span>
                          <h3 className="font-semibold">{stage.name}</h3>
                          <span className="text-xs text-white/40">
                            {stage.description}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {stage.status === 'healing' && (
                            <span className="text-xs text-red-400 flex items-center gap-1">
                              <Heart className="w-3 h-3 animate-pulse" />
                              Heal Agent fixing...
                            </span>
                          )}
                          {stage.status === 'passed' && stage.duration && (
                            <span className="text-xs text-emerald-400">
                              {formatTime(stage.duration)}
                            </span>
                          )}
                          {stage.status === 'failed' && stage.failures && (
                            <span className="text-xs text-red-400">
                              {stage.failures} failure(s)
                            </span>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  </div>
                </div>
              )
            })}
          </div>
        </motion.div>

        {/* Security Posture Gauge */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm"
        >
          <h2 className="text-lg font-semibold mb-6">Security Posture</h2>
          <div className="flex flex-col items-center">
            <div className="relative w-44 h-44">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth="8"
                />
                <motion.circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  strokeWidth="8"
                  strokeLinecap="round"
                  className={getScoreColor(securityScore)}
                  initial={{ strokeDasharray: '0 264' }}
                  animate={{
                    strokeDasharray: `${(securityScore / 100) * 264} 264`,
                  }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-4xl font-bold ${getScoreBgColor(securityScore)}`}>
                  {securityScore}
                </span>
                <span className="text-xs text-white/50">Security Score</span>
              </div>
            </div>
            <div className="mt-6 w-full space-y-3">
              <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">SAST Findings</span>
                  <span>{mockSecurityBreakdown.sast.count}</span>
                </div>
                <div className="flex gap-2 mt-1 text-[10px]">
                  <span className="text-red-400">C:{mockSecurityBreakdown.sast.critical}</span>
                  <span className="text-orange-400">H:{mockSecurityBreakdown.sast.high}</span>
                  <span className="text-amber-400">M:{mockSecurityBreakdown.sast.medium}</span>
                  <span className="text-white/40">L:{mockSecurityBreakdown.sast.low}</span>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">DAST Results</span>
                <span>{mockSecurityBreakdown.dast.count}</span>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Secret Scan</span>
                <span className={mockSecurityBreakdown.secretScan === 'pass' ? 'text-emerald-400' : 'text-red-400'}>
                  {mockSecurityBreakdown.secretScan === 'pass' ? 'Pass' : 'Fail'}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Dependency Audit</span>
                <span>{mockSecurityBreakdown.dependencyAudit} vulnerable</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Agent Activity Logs */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-[#0a0a0f] border border-white/10 rounded-2xl overflow-hidden"
      >
        <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-sm font-medium">Agent Activity Logs</span>
        </div>
        <div
          className="h-48 overflow-y-auto font-mono text-xs p-4 space-y-1"
          style={{ maxHeight: 200 }}
        >
          <AnimatePresence mode="popLayout">
            {agentLogs.map((log) => (
              <motion.div
                key={log.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex gap-3"
              >
                <span className="text-white/30 shrink-0">{log.timestamp}</span>
                <span className={`shrink-0 font-semibold ${AGENT_COLORS[log.agent] || 'text-white/60'}`}>
                  [{log.agent}]
                </span>
                <span className="text-white/70 break-all">{log.message}</span>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={logsEndRef} />
        </div>
      </motion.div>

      {/* Worker Vitals */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold">Worker Vitals</h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-xs text-white/50">Simulated</span>
          </div>
        </div>

        {/* Resource Gauges */}
        <div className="grid grid-cols-3 gap-6 mb-6">
          {/* CPU Gauge */}
          <div className="flex flex-col items-center">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  strokeWidth="6"
                  strokeLinecap="round"
                  className={cpuUsage > 80 ? 'stroke-red-500' : cpuUsage > 50 ? 'stroke-amber-500' : 'stroke-emerald-500'}
                  strokeDasharray={`${(cpuUsage / 100) * 264} 264`}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold">{Math.round(cpuUsage)}%</span>
                <span className="text-[10px] text-white/40">CPU</span>
              </div>
            </div>
          </div>

          {/* Memory Gauge */}
          <div className="flex flex-col items-center">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  strokeWidth="6"
                  strokeLinecap="round"
                  className={
                    (memoryUsage / memoryTotal) * 100 > 80
                      ? 'stroke-red-500'
                      : (memoryUsage / memoryTotal) * 100 > 50
                        ? 'stroke-amber-500'
                        : 'stroke-emerald-500'
                  }
                  strokeDasharray={`${(memoryUsage / memoryTotal) * 264} 264`}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold">{memoryUsage.toFixed(1)}</span>
                <span className="text-[10px] text-white/40">/ {memoryTotal} GB</span>
              </div>
            </div>
          </div>

          {/* Active Agents */}
          <div className="flex flex-col items-center justify-center">
            <div className="text-3xl font-bold text-cyan-400">{activeAgents}</div>
            <div className="text-xs text-white/40">/ {maxAgents} agents</div>
          </div>
        </div>

        {/* Throttle Slider */}
        <div className="mb-6 p-4 rounded-xl bg-black/30 border border-white/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Agent Concurrency Limit</span>
            <span className="text-sm font-mono text-cyan-400">{throttleLimit}</span>
          </div>
          <input
            type="range"
            min="1"
            max="16"
            value={throttleLimit}
            onChange={(e) => setThrottleLimit(Number(e.target.value))}
            className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <p className="text-[10px] text-white/40 mt-1">
            Limits the number of concurrent AI agent processes to prevent resource exhaustion
          </p>
        </div>

        {/* Process Table */}
        <div className="overflow-hidden rounded-lg border border-white/5">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-black/30 text-white/50">
                <th className="px-3 py-2 text-left font-medium">PID</th>
                <th className="px-3 py-2 text-left font-medium">Agent</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">CPU %</th>
                <th className="px-3 py-2 text-right font-medium">Mem MB</th>
                <th className="px-3 py-2 text-right font-medium">Uptime</th>
              </tr>
            </thead>
            <tbody>
              {workerProcesses.map((proc) => (
                <tr
                  key={proc.pid}
                  className={`border-t border-white/5 ${proc.status === 'running' ? 'bg-emerald-500/5' : 'bg-white/[0.02]'}`}
                >
                  <td className="px-3 py-2 font-mono text-white/60">{proc.pid}</td>
                  <td className="px-3 py-2 font-medium">{proc.name}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                        proc.status === 'running' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white/40'
                      }`}
                    >
                      <div
                        className={`w-1.5 h-1.5 rounded-full ${proc.status === 'running' ? 'bg-emerald-400 animate-pulse' : 'bg-white/30'}`}
                      />
                      {proc.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{proc.cpu.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right font-mono">{proc.memory}</td>
                  <td className="px-3 py-2 text-right text-white/50">{proc.uptime}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Chaos & Resilience */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.28 }}
        className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-rose-400" />
            <h2 className="text-lg font-semibold">Chaos & Resilience</h2>
          </div>
          <div className="flex items-center gap-4">
            {/* Adversarial Hygiene Badge */}
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-black/30 border border-white/5">
              <ShieldAlert className="w-4 h-4 text-yellow-400" />
              <span className="text-xs text-white/60">Adversarial Hygiene:</span>
              <span className={`text-xs font-bold ${adversarialScore >= 90 ? 'text-emerald-400' : adversarialScore >= 70 ? 'text-amber-400' : 'text-red-400'}`}>
                {adversarialScore}%
              </span>
            </div>
            {/* Chaos Mode Toggle */}
            <button
              onClick={() => {
                setChaosEnabled(!chaosEnabled)
                addLog('Chaos', chaosEnabled ? 'Chaos Mode DISABLED' : 'Chaos Mode ENABLED — Monkey Testing active')
              }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                chaosEnabled
                  ? 'bg-rose-500/20 border border-rose-500/40 text-rose-400'
                  : 'bg-white/5 border border-white/10 text-white/50 hover:text-white/70'
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${chaosEnabled ? 'bg-rose-400 animate-pulse' : 'bg-white/30'}`} />
              {chaosEnabled ? 'Chaos ON' : 'Chaos OFF'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
          {/* Left: Chaos Events + Controls */}
          <div className="space-y-4">
            {/* Chaos Intensity Slider */}
            <div className="p-4 rounded-xl bg-black/30 border border-white/5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Chaos Intensity</span>
                <span className={`text-sm font-mono ${chaosIntensity > 70 ? 'text-red-400' : chaosIntensity > 40 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {chaosIntensity}%
                </span>
              </div>
              <input
                type="range" min="5" max="100" value={chaosIntensity}
                onChange={(e) => setChaosIntensity(Number(e.target.value))}
                className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
              <div className="flex justify-between text-[10px] text-white/30 mt-1">
                <span>Light disruption</span>
                <span>Full chaos</span>
              </div>
            </div>

            {/* Injected Faults Table */}
            <div className="overflow-hidden rounded-lg border border-white/5">
              <div className="px-3 py-2 bg-black/30 border-b border-white/5 flex items-center justify-between">
                <span className="text-xs font-medium text-white/60">Injected Faults</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-white/40">{chaosEvents.length} events</span>
                  <button
                    onClick={() => { setChaosEvents([]); addLog('Chaos', 'Injected faults cleared.') }}
                    className="text-[10px] text-white/40 hover:text-white/70 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              </div>
              <div className="max-h-[200px] overflow-y-auto">
                {chaosEvents.map((event) => (
                  <div key={event.id} className={`flex items-center justify-between px-3 py-2 text-xs border-t border-white/5 ${
                    event.recovered ? 'bg-white/[0.02]' : 'bg-red-500/5'
                  }`}>
                    <div className="flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${event.recovered ? 'bg-emerald-400' : 'bg-red-400 animate-pulse'}`} />
                      <span className="font-mono text-white/50">{event.timestamp}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        event.type === 'process_kill' ? 'bg-red-500/20 text-red-400' :
                        event.type === 'latency_injection' ? 'bg-amber-500/20 text-amber-400' :
                        event.type === 'network_partition' ? 'bg-purple-500/20 text-purple-400' :
                        event.type === 'memory_pressure' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-orange-500/20 text-orange-400'
                      }`}>
                        {event.type.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-white/40">{event.target}</span>
                      <span className={`font-mono ${event.recovered ? 'text-emerald-400' : 'text-red-400'}`}>
                        {event.recoveryMs}ms
                      </span>
                      <span className={`text-[10px] font-medium ${event.recovered ? 'text-emerald-400' : 'text-red-400'}`}>
                        {event.recovered ? 'RECOVERED' : 'FAILED'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  addLog('RedTeam', 'Red Team scan initiated — searching for logic exploits...')
                  setTimeout(() => {
                    const findings = Math.floor(Math.random() * 5) + 2
                    setRedTeamFindings(findings)
                    setResilienceScore(prev => Math.max(0, Math.min(100, prev - findings * 2)))
                    addLog('RedTeam', `Red Team scan complete. Found ${findings} potential exploits.`)
                  }, 2000)
                }}
                className="flex items-center gap-2 px-4 py-2 bg-violet-500/20 border border-violet-500/30 hover:bg-violet-500/30 rounded-lg text-xs font-medium text-violet-400 transition-colors"
              >
                <Target className="w-3.5 h-3.5" />
                Run Red Team Scan
              </button>
              <button
                onClick={() => {
                  addLog('Adversarial', 'Adversarial hygiene test started — 15 jailbreak prompts...')
                  setTimeout(() => {
                    const score = 90 + Math.floor(Math.random() * 11)
                    setAdversarialScore(score)
                    addLog('Adversarial', `Adversarial hygiene: ${score}% — ${score >= 100 ? 'PERFECT' : (15 - Math.floor(score * 15 / 100)) + ' prompts bypassed'}`)
                  }, 1500)
                }}
                className="flex items-center gap-2 px-4 py-2 bg-yellow-500/20 border border-yellow-500/30 hover:bg-yellow-500/30 rounded-lg text-xs font-medium text-yellow-400 transition-colors"
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                Adversarial Hygiene Test
              </button>
            </div>
          </div>

          {/* Right: Resilience Score + RTO */}
          <div className="space-y-4">
            {/* Resilience Score Gauge */}
            <div className="flex flex-col items-center p-4 rounded-xl bg-black/30 border border-white/5">
              <div className="relative w-28 h-28 mb-2">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
                  <circle cx="50" cy="50" r="42" fill="none" strokeWidth="6" strokeLinecap="round"
                    className={resilienceScore > 70 ? 'stroke-emerald-500' : resilienceScore > 40 ? 'stroke-amber-500' : 'stroke-red-500'}
                    strokeDasharray={`${(resilienceScore / 100) * 264} 264`}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-2xl font-bold ${resilienceScore > 70 ? 'text-emerald-400' : resilienceScore > 40 ? 'text-amber-400' : 'text-red-400'}`}>
                    {resilienceScore}
                  </span>
                  <span className="text-[10px] text-white/40">Resilience</span>
                </div>
              </div>
              <span className="text-xs text-white/50">Recovery Success Rate</span>
            </div>

            {/* RTO Stats */}
            <div className="space-y-2">
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Avg Recovery (RTO)</span>
                <span className="font-mono text-emerald-400">
                  {Math.round(chaosEvents.filter(e => e.recovered).reduce((a, e) => a + e.recoveryMs, 0) / Math.max(chaosEvents.filter(e => e.recovered).length, 1))}ms
                </span>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Max Recovery</span>
                <span className="font-mono text-amber-400">
                  {Math.max(...chaosEvents.map(e => e.recoveryMs))}ms
                </span>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Red Team Findings</span>
                <span className={`font-mono ${redTeamFindings > 3 ? 'text-red-400' : redTeamFindings > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {redTeamFindings}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-black/30 border border-white/5 flex justify-between text-sm">
                <span className="text-white/60">Faults Injected</span>
                <span className="font-mono text-rose-400">{chaosEvents.length}</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Bottom Bar */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex items-center justify-between py-4 px-6 bg-white/5 border border-white/10 rounded-xl"
      >
        <div className="flex items-center gap-6">
          <button
            onClick={handleExportReport}
            className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/15 rounded-lg font-medium text-sm transition-colors"
          >
            <Download className="w-4 h-4" />
            Export Titan Audit Report
          </button>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isQuarantined ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'
              }`}
            />
            <span className="text-sm text-white/60">
              Quarantine: {isQuarantined ? 'Active' : 'None'}
            </span>
          </div>
          <span className="text-sm text-white/40 flex items-center gap-1">
            <Clock className="w-4 h-4" />
            Last scan: {lastScanTime || 'Never'}
          </span>
        </div>
      </motion.div>
        </>
      )}

      {guardianTab === 'governance' && (
        <div className="space-y-6">
          {/* Governance Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: 'Project License', value: mockProjectLicense.licenseId, sub: mockProjectLicense.category, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20', icon: Scale },
              { label: 'Violations', value: mockViolations.length.toString(), sub: 'blocked transfers', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', icon: Ban },
              { label: 'Provenance Records', value: mockProvenanceRecords.length.toString(), sub: `${mockProvenanceRecords.filter(r => r.verified).length} verified`, color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/20', icon: BookOpen },
              { label: 'Toxic Patterns', value: mockToxicMatches.length.toString(), sub: `${mockToxicMatches.filter(m => m.blocked).length} blocked`, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', icon: FileSearch },
            ].map((stat) => {
              const Icon = stat.icon
              return (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-4 rounded-xl border ${stat.bg}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Icon className={`w-5 h-5 ${stat.color}`} />
                  </div>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <div className="text-xs text-white/40">{stat.label}</div>
                  <div className="text-[10px] text-white/30 mt-0.5">{stat.sub}</div>
                </motion.div>
              )
            })}
          </div>

          {/* Two Column: License Matrix + Violations */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* License Compatibility Matrix */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white/5 border border-white/10 rounded-2xl p-6"
            >
              <div className="flex items-center gap-3 mb-4">
                <Scale className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-semibold">License Compatibility Matrix</h2>
              </div>
              <div className="overflow-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      <th className="px-2 py-2 text-left text-white/40 font-medium">Source ↓ / Target →</th>
                      {mockLicenseMatrix.categories.map(cat => (
                        <th key={cat} className="px-2 py-2 text-center text-white/40 font-medium text-[10px]">
                          {cat.replace('_', ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mockLicenseMatrix.categories.map(src => (
                      <tr key={src} className="border-t border-white/5">
                        <td className="px-2 py-2 text-white/60 font-medium text-[10px]">
                          {src.replace('_', ' ')}
                        </td>
                        {mockLicenseMatrix.categories.map(tgt => {
                          const ok = mockLicenseMatrix.matrix[src]?.[tgt] ?? false
                          return (
                            <td key={tgt} className="px-2 py-2 text-center">
                              <span className={`inline-block w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold ${
                                ok ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                              }`}>
                                {ok ? '✓' : '✗'}
                              </span>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex gap-4 mt-3 text-[10px] text-white/30">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/20" /> Compatible</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/20" /> Incompatible</span>
              </div>
            </motion.div>

            {/* License Violations */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-white/5 border border-white/10 rounded-2xl p-6"
            >
              <div className="flex items-center gap-3 mb-4">
                <Ban className="w-5 h-5 text-red-400" />
                <h2 className="text-lg font-semibold">License Violations</h2>
                <span className="text-xs text-white/30 ml-auto">{mockViolations.length} total</span>
              </div>
              <div className="space-y-3">
                {mockViolations.map(v => (
                  <div key={v.id} className="p-3 rounded-lg bg-red-500/5 border border-red-500/10">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium uppercase ${
                          v.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                        }`}>
                          {v.severity}
                        </span>
                        <span className="text-sm font-mono">{v.source} → {v.target}</span>
                      </div>
                      {v.blocked && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium">BLOCKED</span>
                      )}
                    </div>
                    <p className="text-xs text-white/60">{v.description}</p>
                    <div className="flex items-center gap-3 mt-1 text-[10px] text-white/30">
                      <span>{v.file}</span>
                      <span>{v.timestamp}</span>
                    </div>
                  </div>
                ))}
                {mockViolations.length === 0 && (
                  <p className="text-sm text-white/40 text-center py-4">No violations detected</p>
                )}
              </div>
            </motion.div>
          </div>

          {/* AI Provenance & Attribution */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="bg-white/5 border border-white/10 rounded-2xl p-6"
          >
            <div className="flex items-center gap-3 mb-4">
              <Eye className="w-5 h-5 text-cyan-400" />
              <h2 className="text-lg font-semibold">AI Provenance & Attribution</h2>
              <span className="text-xs text-white/30 ml-auto">
                {mockProvenanceRecords.filter(r => r.applied).length} applied / {mockProvenanceRecords.length} total
              </span>
            </div>
            <div className="space-y-2">
              {mockProvenanceRecords.map(rec => (
                <div key={rec.id} className={`p-3 rounded-lg border ${
                  rec.verified ? 'bg-emerald-500/5 border-emerald-500/10' : 'bg-white/[0.02] border-white/5'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        rec.source === 'wisdom_nugget' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {rec.source === 'wisdom_nugget' ? 'Wisdom' : 'AI Gen'}
                      </span>
                      <span className="text-sm font-mono text-white/80">{rec.file}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {rec.verified && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Verified
                        </span>
                      )}
                      {rec.applied && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-medium">Applied</span>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-white/60">{rec.change}</p>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-white/30">
                    {rec.nuggetProject && <span>Source: {rec.nuggetProject}</span>}
                    {rec.license && <span>License: {rec.license}</span>}
                    <span>{rec.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Toxic Snippet Scanner */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white/5 border border-white/10 rounded-2xl p-6"
          >
            <div className="flex items-center gap-3 mb-4">
              <FileSearch className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-semibold">Toxic Snippet Scanner</h2>
              <span className="text-xs text-white/30 ml-auto">{mockToxicMatches.length} patterns flagged</span>
            </div>
            <div className="space-y-3">
              {mockToxicMatches.map(m => (
                <div key={m.id} className={`p-3 rounded-lg border ${
                  m.severity === 'critical' ? 'bg-red-500/5 border-red-500/10' : 'bg-amber-500/5 border-amber-500/10'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium uppercase ${
                        m.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {m.severity}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        m.category === 'ethical' ? 'bg-purple-500/20 text-purple-400' :
                        m.category === 'bias' ? 'bg-pink-500/20 text-pink-400' :
                        m.category === 'malware' ? 'bg-red-500/20 text-red-400' :
                        'bg-orange-500/20 text-orange-400'
                      }`}>
                        {m.category}
                      </span>
                      <span className="text-xs font-mono text-white/50">{m.pattern}</span>
                    </div>
                    {m.blocked && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium">BLOCKED</span>
                    )}
                  </div>
                  <p className="text-xs text-white/60">{m.description}</p>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-white/30">
                    <span>{m.file}:{m.line}</span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Governance Bottom Bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="flex items-center justify-between py-4 px-6 bg-white/5 border border-white/10 rounded-xl"
          >
            <div className="flex items-center gap-4">
              <button
                onClick={() => {
                  const report = `# Legal & Ethics Report\nGenerated: ${new Date().toISOString()}\n\n## License: ${mockProjectLicense.licenseId}\n## Violations: ${mockViolations.length}\n## Provenance Records: ${mockProvenanceRecords.length}\n## Toxic Matches: ${mockToxicMatches.length}`
                  const blob = new Blob([report], { type: 'text/markdown' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `governance-report-${new Date().toISOString().slice(0, 10)}.md`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
              >
                <Download className="w-4 h-4" />
                Export Governance Report
              </button>
              <button
                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/15 rounded-lg font-medium text-sm transition-colors"
              >
                <FileSearch className="w-4 h-4" />
                Run Full Toxic Scan
              </button>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${mockViolations.length > 0 ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`} />
              <span className="text-sm text-white/60">
                Legal Gate: {mockViolations.length > 0 ? 'Violations Detected' : 'All Clear'}
              </span>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
