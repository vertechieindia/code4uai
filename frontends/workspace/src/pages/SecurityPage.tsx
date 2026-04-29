import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../AuthContext'
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Lock,
  Bug,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronRight,
  KeyRound,
  Database,
} from 'lucide-react'

const API = '/api/v1'

interface SecurityFinding {
  type: string
  name: string
  severity: string
  filePath: string
  line: number
  description: string
  match?: string
  fix?: string
  category?: string
  ruleId?: string
  patternId?: string
}

interface VulnEntry {
  package: string
  currentVersion: string
  cve: string
  severity: string
  title: string
  fixedVersion: string
  ecosystem: string
}

export default function SecurityPage() {
  const { token } = useAuth()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const [loading, setLoading] = useState(false)
  const [findings, setFindings] = useState<SecurityFinding[]>([])
  const [vulns, setVulns] = useState<VulnEntry[]>([])
  const [riskLevel, setRiskLevel] = useState('')
  const [scannedFiles, setScannedFiles] = useState(0)
  const [totalPackages, setTotalPackages] = useState(0)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['secrets', 'vulns', 'sast']))
  const [workspacePath] = useState(() => localStorage.getItem('code4u_workspace') || '')

  const runSecurityScan = useCallback(async () => {
    if (!workspacePath) return
    setLoading(true)
    try {
      const [secRes, vulnRes] = await Promise.all([
        fetch(`${API}/sentinel/security-workspace`, {
          method: 'POST', headers,
          body: JSON.stringify({ workspacePath, maxFiles: 50 }),
        }),
        fetch(`${API}/sentinel/vulnerabilities`, {
          method: 'POST', headers,
          body: JSON.stringify({ workspacePath }),
        }),
      ])

      if (secRes.ok) {
        const secData = await secRes.json()
        setFindings(secData.findings || [])
        setScannedFiles(secData.scannedFiles || 0)
        setRiskLevel(secData.riskLevel || 'low')
      }

      if (vulnRes.ok) {
        const vulnData = await vulnRes.json()
        setVulns(vulnData.vulnerabilities || [])
        setTotalPackages(vulnData.totalPackages || 0)
        if (vulnData.riskLevel === 'critical' || vulnData.riskLevel === 'high') {
          setRiskLevel(vulnData.riskLevel)
        }
      }
    } catch {}
    setLoading(false)
  }, [workspacePath, token])

  useEffect(() => {
    if (workspacePath) runSecurityScan()
  }, [workspacePath])

  const secrets = findings.filter(f => f.type === 'secret' || f.type === 'high-entropy')
  const sastFindings = findings.filter(f => f.type === 'vulnerability')
  const criticalSecrets = secrets.filter(f => f.severity === 'critical')
  const criticalVulns = vulns.filter(v => v.severity === 'critical')

  const toggleSection = (s: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      next.has(s) ? next.delete(s) : next.add(s)
      return next
    })
  }

  const severityColor = (s: string) => {
    switch (s) {
      case 'critical': return 'text-red-400 bg-red-500/10'
      case 'high': return 'text-orange-400 bg-orange-500/10'
      case 'warning': return 'text-amber-400 bg-amber-500/10'
      case 'medium': return 'text-amber-400 bg-amber-500/10'
      default: return 'text-blue-400 bg-blue-500/10'
    }
  }

  const riskConfig = {
    critical: { icon: ShieldAlert, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', label: 'Critical Risk' },
    high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', label: 'High Risk' },
    medium: { icon: Shield, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', label: 'Medium Risk' },
    low: { icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', label: 'Low Risk' },
  }

  const risk = riskConfig[riskLevel as keyof typeof riskConfig] || riskConfig.low
  const RiskIcon = risk.icon

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Shield className="w-7 h-7 text-emerald-400" />
            Security & Compliance
          </h1>
          <p className="text-white/50 mt-1">
            Secret detection, vulnerability scanning, and security governance
          </p>
        </div>
        <button
          onClick={runSecurityScan}
          disabled={loading || !workspacePath}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold hover:shadow-lg hover:shadow-emerald-500/25 transition-all disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {loading ? 'Scanning...' : 'Run Scan'}
        </button>
      </div>

      {!workspacePath && (
        <div className="text-center py-16 text-white/30">
          <Lock className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>Open a project first to run security scans.</p>
        </div>
      )}

      {workspacePath && (
        <>
          {/* Risk Overview Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className={`rounded-xl border p-5 ${risk.bg}`}>
              <div className="flex items-center gap-2 mb-2">
                <RiskIcon className={`w-5 h-5 ${risk.color}`} />
                <span className="text-sm font-semibold text-white/70">Overall Risk</span>
              </div>
              <p className={`text-2xl font-bold ${risk.color}`}>{risk.label}</p>
              <p className="text-xs text-white/30 mt-1">{scannedFiles} files scanned</p>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-2">
                <KeyRound className="w-5 h-5 text-red-400" />
                <span className="text-sm font-semibold text-white/70">Secrets</span>
              </div>
              <p className="text-2xl font-bold text-red-400">{secrets.length}</p>
              <p className="text-xs text-white/30 mt-1">{criticalSecrets.length} critical</p>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-5 h-5 text-orange-400" />
                <span className="text-sm font-semibold text-white/70">CVEs</span>
              </div>
              <p className="text-2xl font-bold text-orange-400">{vulns.length}</p>
              <p className="text-xs text-white/30 mt-1">{criticalVulns.length} critical, {totalPackages} packages</p>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-2">
                <Bug className="w-5 h-5 text-amber-400" />
                <span className="text-sm font-semibold text-white/70">SAST Issues</span>
              </div>
              <p className="text-2xl font-bold text-amber-400">{sastFindings.length}</p>
              <p className="text-xs text-white/30 mt-1">{sastFindings.filter(f => f.severity === 'critical').length} critical</p>
            </div>
          </div>

          {loading && findings.length === 0 && (
            <div className="flex items-center justify-center py-16 text-white/40">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Running security scan...
            </div>
          )}

          {/* Secrets Section */}
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('secrets')}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedSections.has('secrets') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <KeyRound className="w-5 h-5 text-red-400" />
                <span className="font-semibold">Secret & Credential Detection</span>
                {secrets.length > 0 && (
                  <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full font-bold">
                    {secrets.length}
                  </span>
                )}
              </div>
              {secrets.length === 0 && (
                <span className="text-xs text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> No secrets found
                </span>
              )}
            </button>
            {expandedSections.has('secrets') && secrets.length > 0 && (
              <div className="divide-y divide-white/5">
                {secrets.map((s, i) => (
                  <div key={i} className="px-5 py-3 hover:bg-white/5 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${severityColor(s.severity)}`}>
                          {s.severity.toUpperCase()}
                        </span>
                        <span className="text-sm font-medium">{s.name}</span>
                      </div>
                      <span className="text-xs text-white/30 font-mono">{s.filePath}:{s.line}</span>
                    </div>
                    <p className="text-xs text-white/50">{s.description}</p>
                    {s.match && <p className="text-xs text-white/20 font-mono mt-1">Match: {s.match}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* CVE / Vulnerability Section */}
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('vulns')}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedSections.has('vulns') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <Database className="w-5 h-5 text-orange-400" />
                <span className="font-semibold">Dependency Vulnerabilities (SCA)</span>
                {vulns.length > 0 && (
                  <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs rounded-full font-bold">
                    {vulns.length} CVE{vulns.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {vulns.length === 0 && (
                <span className="text-xs text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> No known CVEs
                </span>
              )}
            </button>
            {expandedSections.has('vulns') && vulns.length > 0 && (
              <div className="divide-y divide-white/5">
                {vulns.map((v, i) => (
                  <div key={i} className="px-5 py-3 hover:bg-white/5 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${severityColor(v.severity)}`}>
                          {v.severity.toUpperCase()}
                        </span>
                        <span className="text-sm font-medium">{v.package}</span>
                        <span className="text-xs text-white/30">{v.currentVersion}</span>
                      </div>
                      <span className="text-xs text-white/40 font-mono">{v.cve}</span>
                    </div>
                    <p className="text-xs text-white/50">{v.title}</p>
                    {v.fixedVersion && (
                      <p className="text-xs text-emerald-400 mt-1">
                        Fix: upgrade to {v.fixedVersion}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* SAST Section */}
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('sast')}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedSections.has('sast') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <Bug className="w-5 h-5 text-amber-400" />
                <span className="font-semibold">Static Security Analysis (SAST)</span>
                {sastFindings.length > 0 && (
                  <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded-full font-bold">
                    {sastFindings.length}
                  </span>
                )}
              </div>
              {sastFindings.length === 0 && (
                <span className="text-xs text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> No vulnerabilities found
                </span>
              )}
            </button>
            {expandedSections.has('sast') && sastFindings.length > 0 && (
              <div className="divide-y divide-white/5">
                {sastFindings.map((f, i) => (
                  <div key={i} className="px-5 py-3 hover:bg-white/5 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${severityColor(f.severity)}`}>
                          {f.severity.toUpperCase()}
                        </span>
                        <span className="text-sm font-medium">{f.category || f.name}</span>
                      </div>
                      <span className="text-xs text-white/30 font-mono">{f.filePath}:{f.line}</span>
                    </div>
                    <p className="text-xs text-white/50">{f.description}</p>
                    {f.fix && (
                      <p className="text-xs text-cyan-400 mt-1">Fix: {f.fix}</p>
                    )}
                    {f.match && (
                      <pre className="text-[10px] text-white/20 mt-1 font-mono truncate">{f.match}</pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
