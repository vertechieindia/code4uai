import { useState, useEffect } from 'react'
import './App.css'
import { AnimatedBackground } from './components/AnimatedBackground'

// Types
interface ComplianceResult {
  control_id: string
  control_name: string
  framework: string
  status: string
  details: string
  evidence: Record<string, unknown>
}

interface ComplianceData {
  summary: {
    total: number
    passing: number
    failing: number
    compliance_rate: number
  }
  results: ComplianceResult[]
}

interface PricingTier {
  limits: {
    refactors_per_month: number
    cross_repo_allowed: boolean
    premium_fallback_allowed: boolean
    included_seats: number
  }
  features: Record<string, boolean>
  pricing: {
    base_price_usd: number
    per_seat_usd: number
  }
}

const API_URL = 'http://localhost:8000'

function App() {
  const [compliance, setCompliance] = useState<ComplianceData | null>(null)
  const [tiers, setTiers] = useState<Record<string, PricingTier> | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'compliance' | 'pricing'>('overview')
  const [email, setEmail] = useState('')

  useEffect(() => {
    fetch(`${API_URL}/api/v1/compliance/check`).then(res => res.json()).then(setCompliance).catch(console.error)
    fetch(`${API_URL}/api/v1/billing/tiers`).then(res => res.json()).then(data => setTiers(data.tiers)).catch(console.error)
  }, [])

  const handleGetStarted = () => {
    window.location.href = 'http://localhost:5173/signup'
  }

  const handleWatchDemo = () => {
    const demoSection = document.getElementById('demo-section')
    demoSection?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubmitEmail = (e: React.FormEvent) => {
    e.preventDefault()
    alert(`Thanks! We'll reach out to ${email} shortly.`)
    setEmail('')
  }

  return (
    <div className="min-h-screen bg-[#020617] text-white overflow-x-hidden">
      {/* Advanced Animated Background */}
      <AnimatedBackground />

      {/* Header */}
      <header className="relative z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="code4u.ai" className="w-10 h-10 object-contain" />
            <span className="text-xl font-bold tracking-tight">code4u.ai</span>
          </div>
          <nav className="hidden md:flex items-center gap-1 bg-white/5 rounded-full p-1 backdrop-blur-sm">
            {(['overview', 'compliance', 'pricing'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                  activeTab === tab
                    ? 'bg-white text-black'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>
          <button 
            onClick={handleGetStarted}
            className="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full text-sm font-semibold hover:shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 hover:-translate-y-0.5"
          >
            Get Started
          </button>
        </div>
      </header>

      <main className="relative z-10">
        {activeTab === 'overview' && <LandingPage onGetStarted={handleGetStarted} onWatchDemo={handleWatchDemo} email={email} setEmail={setEmail} onSubmitEmail={handleSubmitEmail} compliance={compliance} />}
        {activeTab === 'compliance' && <ComplianceTab compliance={compliance} />}
        {activeTab === 'pricing' && <PricingTab tiers={tiers} onGetStarted={handleGetStarted} />}
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 mt-20">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            <div className="col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <img src="/logo.png" alt="code4u.ai" className="w-8 h-8" />
                <span className="text-lg font-bold">code4u.ai</span>
              </div>
              <p className="text-white/60 text-sm max-w-xs mb-6">
                The AI engineering platform that executes verified changes at enterprise scale.
              </p>
              <div className="flex gap-4">
                <SocialIcon name="twitter" />
                <SocialIcon name="github" />
                <SocialIcon name="linkedin" />
              </div>
            </div>
            <FooterColumn title="Product" links={['Features', 'Pricing', 'Security', 'Roadmap']} />
            <FooterColumn title="Resources" links={['Documentation', 'API Reference', 'Changelog', 'Status']} />
            <FooterColumn title="Company" links={['About', 'Blog', 'Careers', 'Contact']} />
          </div>
          <div className="border-t border-white/5 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-white/50 text-sm">© 2026 code4u.ai. All rights reserved.</p>
            <div className="flex items-center gap-6 text-sm text-white/50">
              <span className="flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> SOC 2 Type II</span>
              <span className="flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> ISO 27001</span>
              <span className="flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> GDPR</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

// Landing Page Component
function LandingPage({ onGetStarted, onWatchDemo, email, setEmail, onSubmitEmail, compliance }: {
  onGetStarted: () => void
  onWatchDemo: () => void
  email: string
  setEmail: (email: string) => void
  onSubmitEmail: (e: React.FormEvent) => void
  compliance: ComplianceData | null
}) {
  return (
    <>
      {/* Hero Section */}
      <section className="relative pt-20 pb-32">
        <div className="max-w-7xl mx-auto px-6">
          {/* Announcement Banner */}
          <div className="flex justify-center mb-8">
            <a href="#ril-section" className="group inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-gradient-to-r from-rose-500/10 to-fuchsia-500/10 border border-rose-500/20 hover:border-rose-500/40 transition-colors">
              <span className="flex items-center gap-2 text-sm">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                </span>
                <span className="text-white/70">NEW: Requirements Intelligence Layer — From meeting to shipped code</span>
              </span>
              <span className="text-rose-400 group-hover:translate-x-1 transition-transform">→</span>
            </a>
          </div>

          {/* Main Headline */}
          <div className="text-center max-w-5xl mx-auto relative z-20">
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.1] mb-8">
              <span className="text-white">Your AI assistant </span>
              <span className="relative">
                <span className="bg-gradient-to-r from-rose-400 via-fuchsia-400 to-violet-400 bg-clip-text text-transparent">hallucinates.</span>
                <svg className="absolute -bottom-2 left-0 w-full" viewBox="0 0 200 8" fill="none">
                  <path d="M1 5.5C47.6667 2.16667 141 -2.5 199 5.5" stroke="url(#strike)" strokeWidth="2" strokeLinecap="round"/>
                  <defs><linearGradient id="strike" x1="0" y1="0" x2="200" y2="0"><stop stopColor="#fb7185"/><stop offset="1" stopColor="#a78bfa"/></linearGradient></defs>
                </svg>
              </span>
              <br />
              <span className="text-white">Ours </span>
              <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">executes.</span>
            </h1>

            <p className="text-xl md:text-2xl text-white/80 max-w-3xl mx-auto mb-12 leading-relaxed">
              Stop gambling with probabilistic code generation. <br className="hidden md:block" />
              <span className="text-white font-medium">code4u.ai</span> delivers deterministic, validated refactors across your entire codebase.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
              <button 
                onClick={onGetStarted}
                className="group relative px-8 py-4 bg-white text-black rounded-full font-semibold text-lg overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-white/20 hover:-translate-y-1"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Start Building Free
                  <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                  </svg>
                </span>
              </button>
              <button 
                onClick={onWatchDemo}
                className="group px-8 py-4 rounded-full font-semibold text-lg border border-white/20 hover:bg-white/5 transition-all duration-300 flex items-center gap-3"
              >
                <span className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-colors">
                  <svg className="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                </span>
                Watch Demo
              </button>
            </div>

            {/* Social Proof */}
            <div className="flex flex-col items-center gap-6">
              <p className="text-white/60 text-sm uppercase tracking-wider font-medium">Trusted by engineering teams at</p>
              <div className="flex items-center gap-12 text-white/50">
                <span className="text-2xl font-bold hover:text-white/70 transition-colors cursor-default">Fortune 500</span>
                <span className="text-2xl font-bold hover:text-white/70 transition-colors cursor-default">FinTech</span>
                <span className="text-2xl font-bold hover:text-white/70 transition-colors cursor-default">Healthcare</span>
                <span className="text-2xl font-bold hover:text-white/70 transition-colors cursor-default">Gov't</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem/Agitate Section */}
      <section className="py-24 border-y border-white/5 bg-gradient-to-b from-transparent via-red-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-red-500/10 text-red-400 text-sm font-medium mb-6">The Problem</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">AI coding tools are </span>
              <span className="text-red-400">breaking</span>
              <span className="text-white"> production</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <ProblemCard 
              icon="🎲"
              title="Probabilistic chaos"
              description="Every generation is a gamble. Same prompt, different output. No guarantee it even compiles."
              stat="67%"
              statLabel="of AI-generated code requires fixes"
            />
            <ProblemCard 
              icon="🔥"
              title="Silent failures"
              description="Hallucinated APIs, invented imports, broken schemas. You don't find out until production."
              stat="3.2x"
              statLabel="more time debugging AI code"
            />
            <ProblemCard 
              icon="🚫"
              title="Zero accountability"
              description="No audit trail. No ownership awareness. No understanding of your architecture."
              stat="$2.4M"
              statLabel="avg. cost of AI-caused outage"
            />
          </div>
        </div>
      </section>

      {/* Solution Section */}
      <section className="py-32">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-20">
            <span className="inline-block px-4 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium mb-6">The Solution</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">Deterministic. Validated. </span>
              <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">Verified.</span>
            </h2>
            <p className="text-xl text-white/80 max-w-2xl mx-auto">
              code4u.ai doesn't guess. It knows your codebase, validates every change, and executes with surgical precision.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 mb-16">
            <SolutionCard 
              icon={<KnowledgeGraphIcon />}
              title="Knowledge Graph Intelligence"
              description="We build a complete map of your codebase. Every function, every dependency, every relationship. No guessing."
              features={['500+ microservices mapped', 'Cross-repo dependencies', 'Real-time sync']}
              gradient="from-violet-500/20 to-fuchsia-500/20"
            />
            <SolutionCard 
              icon={<StateMachineIcon />}
              title="11-State Execution Machine"
              description="Every change flows through a deterministic state machine. No skipped steps. No partial failures. No surprises."
              features={['Intent → Impact → Plan → Execute', 'Human-in-the-loop checkpoints', 'Automatic rollback']}
              gradient="from-cyan-500/20 to-blue-500/20"
            />
            <SolutionCard 
              icon={<ContractIcon />}
              title="Contract Enforcement"
              description="Every API change, schema update, and breaking modification is validated against explicit contracts."
              features={['Schema validation', 'API versioning', 'Breaking change detection']}
              gradient="from-emerald-500/20 to-teal-500/20"
            />
            <SolutionCard 
              icon={<ShieldIcon />}
              title="Enterprise Compliance"
              description="SOC 2 Type II and ISO 27001 certified. Immutable audit logs. No-AI zones for sensitive code."
              features={['Tenant isolation', 'RBAC on intents', 'Cryptography exclusion zones']}
              gradient="from-amber-500/20 to-orange-500/20"
            />
          </div>
        </div>
      </section>

      {/* Demo Section */}
      <section id="demo-section" className="py-24 border-y border-white/5 bg-gradient-to-b from-transparent via-blue-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium mb-6">See It In Action</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">From prompt to </span>
              <span className="bg-gradient-to-r from-violet-400 via-blue-400 to-emerald-400 bg-clip-text text-transparent">live app</span>
            </h2>
            <p className="text-lg text-white/70 max-w-2xl mx-auto">
              Watch code4u.ai build, test, and deploy a full-stack application from a single prompt in seconds.
            </p>
          </div>

          <EnhancedDemoTerminal />
        </div>
      </section>

      {/* Demo Section 2 - Ticket to Production */}
      <section className="py-24 border-b border-white/5 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-violet-500/10 text-violet-400 text-sm font-medium mb-6">Enterprise Workflow</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">From ticket to </span>
              <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-rose-400 bg-clip-text text-transparent">production</span>
            </h2>
            <p className="text-lg text-white/70 max-w-2xl mx-auto">
              No coders needed. Just approvers. Watch code4u.ai turn a Jira ticket into production-ready code.
            </p>
          </div>

          <TicketToProdDemo />
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <StatBlock value={compliance?.summary.compliance_rate ? `${compliance.summary.compliance_rate}%` : '100%'} label="Compliance Rate" />
            <StatBlock value="<50ms" label="P99 Latency" />
            <StatBlock value="0" label="Hallucinations" />
            <StatBlock value="99.99%" label="Uptime SLA" />
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">Loved by engineering leaders</h2>
            <p className="text-white/70">See what teams are saying about code4u.ai</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <TestimonialCard 
              quote="We went from 3-day refactors to 3-hour verified changes. The ROI is insane."
              author="Sarah Chen"
              role="VP Engineering"
              company="Series C FinTech"
            />
            <TestimonialCard 
              quote="Finally, an AI tool we can actually trust in production. The compliance story sold our CISO."
              author="Marcus Johnson"
              role="Principal Engineer"
              company="Fortune 500 Healthcare"
            />
            <TestimonialCard 
              quote="The Knowledge Graph is magic. It understands our monorepo better than some of our engineers."
              author="Priya Patel"
              role="Staff Engineer"
              company="Unicorn Startup"
            />
          </div>
        </div>
      </section>

      {/* Requirements Intelligence Layer - NEW */}
      <section className="py-24 border-b border-white/5 bg-gradient-to-b from-transparent via-rose-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-rose-500/10 text-rose-400 text-sm font-medium mb-6">Requirements Intelligence</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">From meeting to </span>
              <span className="bg-gradient-to-r from-rose-400 via-fuchsia-400 to-violet-400 bg-clip-text text-transparent">shipped code</span>
            </h2>
            <p className="text-lg text-white/70 max-w-3xl mx-auto">
              Otter stops at transcription. <span className="text-white font-medium">code4u.ai</span> goes all the way to engineering execution. 
              Capture requirements from Slack, Teams, and Zoom — then watch them become production code.
            </p>
          </div>

          <RILPipelineDemo />

          {/* RIL Features Grid */}
          <div className="grid md:grid-cols-3 gap-6 mt-16">
            <RILFeatureCard 
              icon="🎙️"
              title="Capture Everywhere"
              description="Connect to Slack channels, Teams meetings, and Zoom calls. Automatic transcription with speaker identification."
              platforms={['Slack', 'Teams', 'Zoom', 'Meet']}
            />
            <RILFeatureCard 
              icon="🧠"
              title="Intelligent Classification"
              description="AI classifies every statement: requirements, decisions, risks, action items. Not summaries — structured data."
              tags={['Requirements', 'Decisions', 'Risks', 'Actions']}
            />
            <RILFeatureCard 
              icon="📋"
              title="Engineering-Grade Requirements"
              description="Human language becomes machine contracts. Systems, constraints, acceptance criteria — all extracted automatically."
              metrics={['100%', 'traceable']}
            />
          </div>

          {/* Otter Comparison */}
          <div className="mt-16 p-8 rounded-2xl bg-gradient-to-r from-rose-500/10 via-fuchsia-500/10 to-violet-500/10 border border-white/10">
            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div>
                <h3 className="text-2xl font-bold text-white mb-4">Beyond Transcription</h3>
                <p className="text-white/70 mb-6">
                  While Otter.ai gives you meeting notes, code4u.ai gives you shipped features. 
                  The system where decisions turn into production code.
                </p>
                <div className="space-y-3">
                  <OtterComparison feature="Transcription" otter={true} code4u={true} />
                  <OtterComparison feature="Speaker ID" otter={true} code4u={true} />
                  <OtterComparison feature="Summary" otter={true} code4u={true} />
                  <OtterComparison feature="Requirement Extraction" otter={false} code4u={true} />
                  <OtterComparison feature="Knowledge Graph Integration" otter={false} code4u={true} />
                  <OtterComparison feature="Execution Plans" otter={false} code4u={true} />
                  <OtterComparison feature="Agent Implementation" otter={false} code4u={true} />
                  <OtterComparison feature="Production Deployment" otter={false} code4u={true} />
                </div>
              </div>
              <div className="text-center">
                <div className="inline-block p-8 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30">
                  <p className="text-6xl mb-4">🚀</p>
                  <p className="text-xl text-white font-bold mb-2">The Complete Loop</p>
                  <p className="text-white/60 text-sm">Meeting → Requirements → Code → Production</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise Integrations Section - NEW */}
      <section className="py-24 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium mb-6">Integrations</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">Connects to </span>
              <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">everything</span>
            </h2>
            <p className="text-lg text-white/70 max-w-2xl mx-auto">
              Pull requirements from any source. Push code to any destination. Seamless enterprise workflows.
            </p>
          </div>

          <IntegrationGrid />
        </div>
      </section>

      {/* Complete Platform Section */}
      <section className="py-24 border-b border-white/5 bg-gradient-to-b from-transparent via-cyan-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-400 text-sm font-medium mb-6">Complete Platform</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">Everything they offer. </span>
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400 bg-clip-text text-transparent">Built better.</span>
            </h2>
            <p className="text-lg text-white/70 max-w-3xl mx-auto">
              code4u.ai delivers every capability of Cursor, Windsurf, and Antigravity — but with enterprise-grade architecture, deterministic execution, and zero hallucinations.
            </p>
          </div>

          <FeatureComparisonTable />
        </div>
      </section>

      {/* Multi-Surface Section */}
      <section className="py-24 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium mb-6">One Engine, Every Surface</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">Same backend. </span>
              <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">Same rules.</span>
            </h2>
            <p className="text-lg text-white/70 max-w-2xl mx-auto">
              AI makes client generation cheap. We built one powerful engine that powers every surface.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <SurfaceCard 
              icon="🖥️" 
              title="VS Code Extension" 
              description="Agent, diffs, and reviews directly in your IDE"
              status="Live"
            />
            <SurfaceCard 
              icon="⌨️" 
              title="JetBrains Plugin" 
              description="Full support for IntelliJ, PyCharm, WebStorm"
              status="Live"
            />
            <SurfaceCard 
              icon="💬" 
              title="Slack / Teams" 
              description="Trigger refactors and get approvals in chat"
              status="Live"
            />
            <SurfaceCard 
              icon="🌐" 
              title="Web Dashboard" 
              description="Monitor, review, and manage across repos"
              status="Live"
            />
            <SurfaceCard 
              icon="📱" 
              title="Mobile / CLI" 
              description="Approve changes on the go from anywhere"
              status="Live"
            />
            <SurfaceCard 
              icon="🎫" 
              title="20+ Integrations" 
              description="Jira, ServiceNow, Zoom, and more"
              status="Live"
            />
          </div>
        </div>
      </section>

      {/* Architecture Advantage Section */}
      <section className="py-24 border-b border-white/5 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-violet-500/10 text-violet-400 text-sm font-medium mb-6">The Real Moat</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="text-white">They started with UX. </span>
              <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-rose-400 bg-clip-text text-transparent">We started with trust.</span>
            </h2>
            <p className="text-lg text-white/70 max-w-3xl mx-auto">
              Cursor and Windsurf feel magical because they started with UX and added guardrails later. We did the inverse: strong core first, then UX acceleration.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <ArchitectureCard 
              title="Deterministic State Machine"
              description="Every change flows through 11 verified states. No skipped steps. No partial failures. No surprises."
              icon="🔄"
              highlight="They don't have this"
            />
            <ArchitectureCard 
              title="Code Knowledge Graph"
              description="We don't just embed files — we map every function, dependency, and relationship. Complete system understanding."
              icon="🧠"
              highlight="Beyond embeddings"
            />
            <ArchitectureCard 
              title="Contract-Aware Execution"
              description="Every API change, schema update, and breaking modification is validated against explicit contracts before execution."
              icon="📜"
              highlight="Zero API invention"
            />
            <ArchitectureCard 
              title="No-AI Zones"
              description="Explicitly block AI from auth, payments, crypto, and compliance code. Auditors love this."
              icon="🛡️"
              highlight="Enterprise selling point"
            />
          </div>

          <div className="mt-12 p-8 rounded-2xl bg-gradient-to-r from-violet-500/10 via-fuchsia-500/10 to-rose-500/10 border border-white/10">
            <div className="text-center">
              <p className="text-xl text-white/80 italic mb-4">
                "We're not competing on model intelligence. We're competing on engineering execution at scale."
              </p>
              <p className="text-white/50 text-sm">— Investor Pitch, code4u.ai</p>
            </div>
          </div>
        </div>
      </section>

      {/* Roadmap Section */}
      <section className="py-24 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium mb-6">Roadmap</span>
            <h2 className="text-4xl md:text-5xl font-bold mb-6 text-white">Our path to market leadership</h2>
          </div>

          <div className="space-y-8">
            <RoadmapPhase 
              phase="1"
              title="Enterprise Agent Core"
              timeline="Completed ✓"
              status="completed"
              goal="Pilot customers"
              features={[
                "Agent State Machine ✓",
                "Knowledge Graph ✓",
                "Context → Prompt Compiler ✓",
                "Deterministic Execution ✓",
                "VS Code Extension ✓",
                "Enterprise Security ✓"
              ]}
            />
            <RoadmapPhase 
              phase="2"
              title="Platform Expansion"
              timeline="Completed ✓"
              status="completed"
              goal="Paid teams"
              features={[
                "Model Picker & Routing ✓",
                "CLI Agent ✓",
                "Rules & Workflows ✓",
                "JetBrains Plugin ✓",
                "20+ Integrations ✓",
                "Requirements Intelligence ✓"
              ]}
            />
            <RoadmapPhase 
              phase="3"
              title="Developer Delight"
              timeline="Current Phase"
              status="current"
              goal="Market leadership"
              features={[
                "Supercomplete ✓",
                "Browser Agent ✓",
                "MCP Marketplace ✓",
                "Agent Manager ✓",
                "Knowledge & Memories ✓"
              ]}
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-5xl md:text-6xl font-bold mb-8">
            <span className="text-white">Ready to stop </span>
            <span className="bg-gradient-to-r from-rose-400 to-violet-400 bg-clip-text text-transparent">gambling</span>
            <span className="text-white">?</span>
          </h2>
          <p className="text-xl text-white/80 mb-12 max-w-2xl mx-auto">
            Join engineering teams who ship faster, safer, and with complete confidence. No credit card required.
          </p>

          <form onSubmit={onSubmitEmail} className="flex flex-col sm:flex-row gap-4 justify-center max-w-md mx-auto mb-8">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your work email"
              className="flex-1 px-6 py-4 rounded-full bg-white/5 border border-white/10 text-white placeholder:text-white/50 focus:outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 transition-all"
              required
            />
            <button 
              type="submit"
              className="px-8 py-4 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full font-semibold text-lg hover:shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 hover:-translate-y-0.5 whitespace-nowrap"
            >
              Get Early Access
            </button>
          </form>

          <p className="text-white/60 text-sm">
            Free tier available • No credit card required • 5 minute setup
          </p>
        </div>
      </section>
    </>
  )
}

// Problem Card
function ProblemCard({ icon, title, description, stat, statLabel }: { icon: string; title: string; description: string; stat: string; statLabel: string }) {
  return (
    <div className="group relative p-8 rounded-2xl bg-gradient-to-b from-red-500/5 to-transparent border border-red-500/10 hover:border-red-500/20 transition-colors backdrop-blur-sm">
      <span className="text-4xl mb-6 block">{icon}</span>
      <h3 className="text-xl font-semibold text-white mb-3">{title}</h3>
      <p className="text-white/80 mb-6">{description}</p>
      <div className="pt-6 border-t border-white/5">
        <span className="text-3xl font-bold text-red-400">{stat}</span>
        <p className="text-white/70 text-sm mt-1">{statLabel}</p>
      </div>
    </div>
  )
}

// Solution Card
function SolutionCard({ icon, title, description, features, gradient }: { icon: React.ReactNode; title: string; description: string; features: string[]; gradient: string }) {
  return (
    <div className={`group relative p-8 rounded-2xl bg-gradient-to-br ${gradient} border border-white/10 hover:border-white/20 transition-all duration-300 hover:-translate-y-1 backdrop-blur-sm`}>
      <div className="w-14 h-14 rounded-xl bg-white/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-xl font-semibold text-white mb-3">{title}</h3>
      <p className="text-white/80 mb-6">{description}</p>
      <ul className="space-y-2">
        {features.map((feature, i) => (
          <li key={i} className="flex items-center gap-2 text-white text-sm">
            <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            {feature}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Enhanced Demo Terminal - Full App Lifecycle
function EnhancedDemoTerminal() {
  const [phase, setPhase] = useState(0)
  const [typedPrompt, setTypedPrompt] = useState('')
  const [activeFile, setActiveFile] = useState(0)
  
  const prompt = "Build a task management app with React frontend and FastAPI backend"
  
  const phases = [
    { state: 'PROMPT', label: 'Receiving prompt...', icon: '💬' },
    { state: 'PLANNING', label: 'Planning architecture...', icon: '📋' },
    { state: 'GENERATING', label: 'Generating code...', icon: '⚡' },
    { state: 'TESTING', label: 'Running tests...', icon: '🧪' },
    { state: 'PREVIEW', label: 'Starting preview...', icon: '👁️' },
    { state: 'GIT', label: 'Pushing to Git...', icon: '📦' },
    { state: 'DEPLOYING', label: 'Deploying...', icon: '🚀' },
    { state: 'LIVE', label: 'App is live!', icon: '✨' },
  ]

  const generatedFiles = [
    { path: 'frontend/src/App.tsx', lang: 'tsx', status: 'new', lines: 142 },
    { path: 'frontend/src/components/TaskList.tsx', lang: 'tsx', status: 'new', lines: 87 },
    { path: 'frontend/src/components/TaskForm.tsx', lang: 'tsx', status: 'new', lines: 56 },
    { path: 'frontend/src/hooks/useTasks.ts', lang: 'ts', status: 'new', lines: 34 },
    { path: 'backend/app/main.py', lang: 'py', status: 'new', lines: 45 },
    { path: 'backend/app/models/task.py', lang: 'py', status: 'new', lines: 28 },
    { path: 'backend/app/routes/tasks.py', lang: 'py', status: 'new', lines: 67 },
    { path: 'backend/tests/test_tasks.py', lang: 'py', status: 'new', lines: 89 },
  ]

  const testResults = [
    { name: 'test_create_task', status: 'passed', time: '0.02s' },
    { name: 'test_list_tasks', status: 'passed', time: '0.01s' },
    { name: 'test_update_task', status: 'passed', time: '0.03s' },
    { name: 'test_delete_task', status: 'passed', time: '0.01s' },
    { name: 'test_task_validation', status: 'passed', time: '0.02s' },
  ]

  const codeSnippets: Record<string, string> = {
    'App.tsx': `import { TaskList } from './components/TaskList'
import { TaskForm } from './components/TaskForm'
import { useTasks } from './hooks/useTasks'

export default function App() {
  const { tasks, addTask, toggleTask } = useTasks()
  
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-indigo-600 text-white p-6">
        <h1>Task Manager</h1>
      </header>
      <main className="max-w-4xl mx-auto p-6">
        <TaskForm onAdd={addTask} />
        <TaskList tasks={tasks} onToggle={toggleTask} />
      </main>
    </div>
  )
}`,
    'main.py': `from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import tasks

app = FastAPI(title="Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)

app.include_router(tasks.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}`,
    'tasks.py': `from fastapi import APIRouter, HTTPException
from app.models.task import Task, TaskCreate
from typing import List

router = APIRouter(tags=["tasks"])
tasks_db: List[Task] = []

@router.get("/tasks", response_model=List[Task])
async def list_tasks():
    return tasks_db

@router.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate):
    new_task = Task(id=len(tasks_db)+1, **task.dict())
    tasks_db.append(new_task)
    return new_task`,
  }

  // Typing animation for prompt
  useEffect(() => {
    if (phase === 0) {
      let i = 0
      const typeInterval = setInterval(() => {
        if (i <= prompt.length) {
          setTypedPrompt(prompt.slice(0, i))
          i++
        } else {
          clearInterval(typeInterval)
          setTimeout(() => setPhase(1), 500)
        }
      }, 40)
      return () => clearInterval(typeInterval)
    }
  }, [phase])

  // Phase progression
  useEffect(() => {
    if (phase > 0 && phase < phases.length - 1) {
      const duration = phase === 2 ? 4000 : phase === 3 ? 3000 : 2000
      const timer = setTimeout(() => setPhase(p => p + 1), duration)
      return () => clearTimeout(timer)
    } else if (phase >= phases.length - 1) {
      const timer = setTimeout(() => {
        setPhase(0)
        setTypedPrompt('')
        setActiveFile(0)
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [phase])

  // Cycle through files during generation
  useEffect(() => {
    if (phase === 2) {
      const fileInterval = setInterval(() => {
        setActiveFile(f => (f + 1) % generatedFiles.length)
      }, 500)
      return () => clearInterval(fileInterval)
    }
  }, [phase])

  const currentPhase = phases[phase]
  const progress = (phase / (phases.length - 1)) * 100

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#0a0a0f] shadow-2xl shadow-black/50">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#12121a]">
        <div className="flex items-center gap-4">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
            <div className="w-3 h-3 rounded-full bg-[#27ca40]" />
          </div>
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="code4u.ai" className="w-4 h-4" />
            <span className="text-white/60 text-sm font-medium">code4u.ai</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-2xl">{currentPhase.icon}</span>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
            phase === phases.length - 1 
              ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/50' 
              : phase === 0
                ? 'bg-white/5 text-white/40'
                : 'bg-blue-500/20 text-blue-400'
          }`}>
            {phase > 0 && phase < phases.length - 1 && (
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            )}
            {phase === phases.length - 1 && <Check className="w-3 h-3" />}
            <span>{currentPhase.state}</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-white/5">
        <div 
          className="h-full bg-gradient-to-r from-violet-500 via-blue-500 via-cyan-500 to-emerald-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="grid lg:grid-cols-2 min-h-[480px]">
        {/* Left Panel - Terminal Output */}
        <div className="p-6 font-mono text-sm border-r border-white/5 overflow-hidden">
          {/* User Prompt */}
          <div className="mb-6">
            <div className="flex items-center gap-2 text-white/40 text-xs mb-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span>USER PROMPT</span>
            </div>
            <div className="flex items-start gap-3 bg-white/5 rounded-lg p-4 border border-white/10">
              <span className="text-violet-400 text-lg">→</span>
              <div className="flex-1">
                <span className="text-white">{typedPrompt}</span>
                {phase === 0 && <span className="inline-block w-2 h-5 bg-white/60 animate-pulse ml-0.5" />}
              </div>
            </div>
          </div>

          {/* Planning Phase */}
          {phase >= 1 && (
            <div className="mb-4 animate-fade-in">
              <div className="flex items-center gap-2 text-white/60 mb-2">
                <span className="text-violet-400">▸</span>
                <span>Architecture planned</span>
                <span className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded">2 services</span>
              </div>
              <div className="ml-5 flex gap-4 text-xs">
                <div className="flex items-center gap-2 text-cyan-400">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                  React Frontend
                </div>
                <div className="flex items-center gap-2 text-emerald-400">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg>
                  FastAPI Backend
                </div>
              </div>
            </div>
          )}

          {/* Generating Phase */}
          {phase >= 2 && (
            <div className="mb-4 animate-fade-in">
              <div className="flex items-center gap-2 text-white/60 mb-3">
                <span className="text-blue-400">▸</span>
                <span>Generating code</span>
                <span className="text-xs text-white/40">{generatedFiles.length} files</span>
              </div>
              
              {/* Code Preview */}
              <div className="ml-5 bg-[#1a1a24] rounded-lg border border-white/10 overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 bg-white/5 border-b border-white/10">
                  <FileIcon filename={generatedFiles[activeFile].path} />
                  <span className="text-xs text-white/70">{generatedFiles[activeFile].path}</span>
                  <span className="ml-auto text-xs text-emerald-400">+{generatedFiles[activeFile].lines} lines</span>
                </div>
                <div className="p-3 text-xs max-h-32 overflow-hidden">
                  <pre className="text-white/60">
                    {codeSnippets[generatedFiles[activeFile].path.split('/').pop() || ''] || '// Generating...'}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* Testing Phase */}
          {phase >= 3 && (
            <div className="mb-4 animate-fade-in">
              <div className="flex items-center gap-2 text-white/60 mb-2">
                <span className="text-amber-400">▸</span>
                <span>Running tests</span>
              </div>
              <div className="ml-5 space-y-1">
                {testResults.map((test, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs animate-fade-in" style={{ animationDelay: `${i * 150}ms` }}>
                    <span className="text-emerald-400">✓</span>
                    <span className="text-white/60">{test.name}</span>
                    <span className="text-white/30 ml-auto">{test.time}</span>
                  </div>
                ))}
                <div className="mt-2 text-xs text-emerald-400 font-medium">
                  ✓ All 5 tests passed
                </div>
              </div>
            </div>
          )}

          {/* Preview Phase */}
          {phase >= 4 && (
            <div className="mb-4 animate-fade-in flex items-center gap-2 text-white/60">
              <span className="text-emerald-400">✓</span>
              <span>Preview ready</span>
              <span className="text-xs text-cyan-400 underline cursor-pointer">localhost:3000</span>
            </div>
          )}

          {/* Git Phase */}
          {phase >= 5 && (
            <div className="mb-4 animate-fade-in">
              <div className="flex items-center gap-2 text-white/60">
                <span className="text-emerald-400">✓</span>
                <span>Pushed to Git</span>
              </div>
              <div className="ml-5 mt-1 text-xs text-white/40 font-mono">
                → main ← feat/task-manager <span className="text-emerald-400">✓ merged</span>
              </div>
            </div>
          )}

          {/* Deploying Phase */}
          {phase >= 6 && (
            <div className="mb-4 animate-fade-in flex items-center gap-2 text-white/60">
              <span className="text-emerald-400">✓</span>
              <span>Deployed to production</span>
              <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">v1.0.0</span>
            </div>
          )}

          {/* Live Phase */}
          {phase >= 7 && (
            <div className="mt-6 animate-fade-in p-4 rounded-lg bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-500/30 flex items-center justify-center">
                  <Check className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <p className="text-emerald-400 font-bold text-lg">App is Live!</p>
                  <p className="text-emerald-400/60 text-sm">taskmanager.code4u.app</p>
                </div>
              </div>
            </div>
          )}

          {/* Loading State */}
          {phase > 0 && phase < phases.length - 1 && (
            <div className="flex items-center gap-2 text-white/40 text-xs mt-4">
              <div className="w-4 h-4 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
              <span>{currentPhase.label}</span>
            </div>
          )}
        </div>

        {/* Right Panel */}
        <div className="bg-[#0a0a0f] p-4 flex flex-col">
          {/* File Explorer */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider">Generated Files</h4>
              <span className="text-xs text-white/40">{phase >= 2 ? `${generatedFiles.length} files` : '—'}</span>
            </div>
            
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {phase >= 2 ? generatedFiles.map((file, i) => (
                <div 
                  key={i} 
                  className={`flex items-center justify-between p-2 rounded text-xs transition-all cursor-pointer ${
                    activeFile === i && phase === 2 
                      ? 'bg-blue-500/20 border border-blue-500/30' 
                      : 'bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  <div className="flex items-center gap-2">
                    <FileIcon filename={file.path} />
                    <span className="text-white/70">{file.path}</span>
                  </div>
                  <span className="text-emerald-400">+{file.lines}</span>
                </div>
              )) : (
                <div className="text-xs text-white/30 text-center py-8">
                  Waiting for generation...
                </div>
              )}
            </div>
          </div>

          {/* App Preview */}
          {phase >= 4 && (
            <div className="flex-1 animate-fade-in">
              <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider mb-3">Live Preview</h4>
              <div className="bg-white rounded-lg overflow-hidden h-48 relative">
                {/* Mini App Preview */}
                <div className="bg-indigo-600 p-2 text-white text-xs font-medium">
                  Task Manager
                </div>
                <div className="p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded border-2 border-indigo-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-indigo-500" />
                    </div>
                    <span className="text-gray-700 text-xs line-through">Build task manager</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded border-2 border-gray-300" />
                    <span className="text-gray-700 text-xs">Add user authentication</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded border-2 border-gray-300" />
                    <span className="text-gray-700 text-xs">Deploy to production</span>
                  </div>
                </div>
                {phase < 7 && (
                  <div className="absolute inset-0 bg-black/20 flex items-center justify-center">
                    <span className="text-xs text-white bg-black/50 px-3 py-1 rounded-full">Preview</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Lifecycle State */}
          <div className="mt-4 pt-4 border-t border-white/5">
            <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider mb-3">Development Lifecycle</h4>
            <div className="flex flex-wrap gap-1">
              {phases.map((p, i) => (
                <div 
                  key={i}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-all ${
                    i < phase 
                      ? 'bg-emerald-500/20 text-emerald-400' 
                      : i === phase 
                        ? 'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/50' 
                        : 'bg-white/5 text-white/30'
                  }`}
                >
                  <span>{p.icon}</span>
                  <span className="hidden sm:inline">{p.state}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Ticket to Production Demo
function TicketToProdDemo() {
  const [phase, setPhase] = useState(0)
  
  const phases = [
    { state: 'TICKET', label: 'Reading ticket...', icon: '🎫' },
    { state: 'ANALYZING', label: 'Analyzing requirements...', icon: '🔍' },
    { state: 'CODING', label: 'Implementing changes...', icon: '💻' },
    { state: 'TESTING', label: 'Running tests...', icon: '🧪' },
    { state: 'PR_CREATED', label: 'Creating PR...', icon: '📝' },
    { state: 'REVIEW', label: 'Awaiting approval...', icon: '👀' },
    { state: 'APPROVED', label: 'Approved!', icon: '✅' },
    { state: 'DEPLOYING', label: 'Deploying...', icon: '🚀' },
    { state: 'LIVE', label: 'Live in production!', icon: '🎉' },
  ]

  const ticket = {
    id: 'PROJ-1234',
    type: 'Feature',
    priority: 'High',
    title: 'Add dark mode toggle to user settings',
    description: 'Users should be able to toggle between light and dark themes from their profile settings page.',
    assignee: 'code4u.ai',
    reporter: 'Sarah Chen',
    labels: ['frontend', 'ux', 'settings'],
  }

  const changedFiles = [
    { path: 'src/components/Settings/ThemeToggle.tsx', changes: '+45', type: 'added' },
    { path: 'src/hooks/useTheme.ts', changes: '+32', type: 'added' },
    { path: 'src/context/ThemeContext.tsx', changes: '+28', type: 'added' },
    { path: 'src/components/Settings/index.tsx', changes: '+8 -2', type: 'modified' },
    { path: 'src/styles/themes.css', changes: '+67', type: 'added' },
    { path: 'tests/ThemeToggle.test.tsx', changes: '+54', type: 'added' },
  ]

  const prDetails = {
    number: 847,
    branch: 'feat/dark-mode-toggle',
    commits: 3,
    additions: 234,
    deletions: 2,
    checks: { passed: 12, total: 12 },
  }

  useEffect(() => {
    const durations = [2500, 2000, 3000, 2500, 2000, 3000, 1500, 2000, 4000]
    if (phase < phases.length - 1) {
      const timer = setTimeout(() => setPhase(p => p + 1), durations[phase])
      return () => clearTimeout(timer)
    } else {
      const timer = setTimeout(() => setPhase(0), 5000)
      return () => clearTimeout(timer)
    }
  }, [phase])

  const currentPhase = phases[phase]
  const progress = (phase / (phases.length - 1)) * 100

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#0a0a0f] shadow-2xl shadow-black/50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#12121a]">
        <div className="flex items-center gap-4">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
            <div className="w-3 h-3 rounded-full bg-[#27ca40]" />
          </div>
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="code4u.ai" className="w-4 h-4" />
            <span className="text-white/60 text-sm font-medium">code4u.ai × Jira Integration</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-2xl">{currentPhase.icon}</span>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
            phase === phases.length - 1 
              ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/50' 
              : phase === 5
                ? 'bg-amber-500/20 text-amber-400'
                : phase === 6
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-violet-500/20 text-violet-400'
          }`}>
            {phase > 0 && phase < phases.length - 1 && phase !== 5 && phase !== 6 && (
              <div className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
            )}
            {(phase === phases.length - 1 || phase === 6) && <Check className="w-3 h-3" />}
            {phase === 5 && <span className="text-amber-400">⏳</span>}
            <span>{currentPhase.state}</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-white/5">
        <div 
          className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-rose-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="grid lg:grid-cols-2 min-h-[500px]">
        {/* Left Panel - Ticket & Progress */}
        <div className="p-6 border-r border-white/5 overflow-hidden">
          {/* Jira Ticket Card */}
          <div className="mb-6">
            <div className="flex items-center gap-2 text-white/40 text-xs mb-3">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.005 1.005 0 0 0 23.013 0z"/>
              </svg>
              <span>JIRA TICKET</span>
            </div>
            <div className={`bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 rounded-xl p-5 border transition-all duration-500 ${
              phase >= 1 ? 'border-violet-500/30' : 'border-white/10'
            }`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-violet-500/20 text-violet-400 text-xs font-medium rounded">{ticket.id}</span>
                  <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">{ticket.type}</span>
                  <span className="px-2 py-0.5 bg-rose-500/20 text-rose-400 text-xs rounded">{ticket.priority}</span>
                </div>
                {phase >= 1 && (
                  <span className="text-emerald-400 text-xs animate-fade-in">● Processing</span>
                )}
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">{ticket.title}</h3>
              <p className="text-white/60 text-sm mb-4">{ticket.description}</p>
              <div className="flex items-center gap-4 text-xs text-white/40">
                <span>Reporter: <span className="text-white/60">{ticket.reporter}</span></span>
                <span>Assignee: <span className="text-emerald-400 font-medium">{ticket.assignee}</span></span>
              </div>
              <div className="flex gap-2 mt-3">
                {ticket.labels.map((label, i) => (
                  <span key={i} className="px-2 py-0.5 bg-white/5 text-white/50 text-xs rounded">{label}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Progress Steps */}
          <div className="space-y-3">
            {phase >= 1 && (
              <div className="flex items-center gap-3 text-sm animate-fade-in">
                <span className="text-emerald-400">✓</span>
                <span className="text-white/70">Requirements analyzed</span>
                <span className="ml-auto text-xs text-white/40">3 acceptance criteria</span>
              </div>
            )}
            
            {phase >= 2 && (
              <div className="animate-fade-in">
                <div className="flex items-center gap-3 text-sm mb-2">
                  <span className="text-emerald-400">✓</span>
                  <span className="text-white/70">Code implementation complete</span>
                </div>
                <div className="ml-6 text-xs text-white/40 space-y-1">
                  <div>• Created ThemeToggle component</div>
                  <div>• Added useTheme hook</div>
                  <div>• Implemented theme context</div>
                </div>
              </div>
            )}

            {phase >= 3 && (
              <div className="flex items-center gap-3 text-sm animate-fade-in">
                <span className="text-emerald-400">✓</span>
                <span className="text-white/70">All tests passing</span>
                <span className="ml-auto text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">12/12</span>
              </div>
            )}

            {phase >= 4 && (
              <div className="flex items-center gap-3 text-sm animate-fade-in">
                <span className="text-emerald-400">✓</span>
                <span className="text-white/70">Pull request created</span>
                <span className="ml-auto text-xs text-violet-400">#{prDetails.number}</span>
              </div>
            )}

            {phase >= 5 && phase < 6 && (
              <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 animate-fade-in">
                <div className="flex items-center gap-2 text-amber-400 font-medium mb-2">
                  <span>👀</span>
                  <span>Awaiting Your Approval</span>
                </div>
                <p className="text-amber-400/60 text-xs">Review the changes and click approve to deploy to production.</p>
                <button 
                  onClick={() => setPhase(6)}
                  className="mt-3 px-4 py-2 bg-emerald-500 text-black font-semibold rounded-lg hover:bg-emerald-400 transition-colors text-sm"
                >
                  ✓ Approve & Deploy
                </button>
              </div>
            )}

            {phase >= 6 && (
              <div className="flex items-center gap-3 text-sm animate-fade-in">
                <span className="text-emerald-400">✓</span>
                <span className="text-emerald-400 font-medium">Approved by reviewer</span>
              </div>
            )}

            {phase >= 7 && (
              <div className="flex items-center gap-3 text-sm animate-fade-in">
                <span className="text-emerald-400">✓</span>
                <span className="text-white/70">Deployed to production</span>
                <span className="ml-auto text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">v2.4.1</span>
              </div>
            )}

            {phase >= 8 && (
              <div className="mt-4 p-4 rounded-lg bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 animate-fade-in">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/30 flex items-center justify-center">
                    <span className="text-xl">🎉</span>
                  </div>
                  <div>
                    <p className="text-emerald-400 font-bold text-lg">Feature is Live!</p>
                    <p className="text-emerald-400/60 text-sm">Dark mode is now available to all users</p>
                  </div>
                </div>
              </div>
            )}

            {phase > 0 && phase < phases.length - 1 && phase !== 5 && (
              <div className="flex items-center gap-2 text-white/40 text-xs mt-4">
                <div className="w-4 h-4 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                <span>{currentPhase.label}</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - PR & Changes */}
        <div className="bg-[#0a0a0f] p-4 flex flex-col">
          {/* PR Card */}
          {phase >= 4 && (
            <div className="mb-4 animate-fade-in">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider">Pull Request</h4>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  phase >= 6 ? 'bg-violet-500/20 text-violet-400' : 'bg-amber-500/20 text-amber-400'
                }`}>
                  {phase >= 6 ? 'Merged' : 'Open'}
                </span>
              </div>
              <div className="bg-white/[0.02] rounded-lg p-4 border border-white/10">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="w-5 h-5 text-violet-400" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/>
                  </svg>
                  <span className="text-white font-medium">#{prDetails.number}</span>
                  <span className="text-white/40">•</span>
                  <span className="text-white/60 text-sm">{prDetails.branch}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-white/40">
                  <span className="text-emerald-400">+{prDetails.additions}</span>
                  <span className="text-rose-400">-{prDetails.deletions}</span>
                  <span>{prDetails.commits} commits</span>
                  <span className="ml-auto flex items-center gap-1 text-emerald-400">
                    <Check className="w-3 h-3" />
                    {prDetails.checks.passed}/{prDetails.checks.total} checks
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Changed Files */}
          <div className="flex-1">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider">Changed Files</h4>
              <span className="text-xs text-white/40">{phase >= 2 ? `${changedFiles.length} files` : '—'}</span>
            </div>
            
            <div className="space-y-1 max-h-56 overflow-y-auto">
              {phase >= 2 ? changedFiles.map((file, i) => (
                <div 
                  key={i} 
                  className="flex items-center justify-between p-2 rounded text-xs bg-white/[0.02] hover:bg-white/[0.05] transition-colors animate-fade-in"
                  style={{ animationDelay: `${i * 80}ms` }}
                >
                  <div className="flex items-center gap-2">
                    <span className={file.type === 'added' ? 'text-emerald-400' : 'text-amber-400'}>
                      {file.type === 'added' ? '+' : '~'}
                    </span>
                    <FileIcon filename={file.path} />
                    <span className="text-white/70 truncate">{file.path.split('/').pop()}</span>
                  </div>
                  <span className="text-emerald-400 font-mono">{file.changes}</span>
                </div>
              )) : (
                <div className="text-xs text-white/30 text-center py-8">
                  Waiting for implementation...
                </div>
              )}
            </div>
          </div>

          {/* Live Preview */}
          {phase >= 8 && (
            <div className="mt-4 animate-fade-in">
              <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider mb-3">Live Feature</h4>
              <div className="bg-white rounded-lg overflow-hidden">
                <div className="bg-gray-800 p-3 flex items-center justify-between">
                  <span className="text-white text-xs font-medium">Settings</span>
                  <div className="flex items-center gap-2">
                    <span className="text-white/60 text-xs">Dark Mode</span>
                    <div className="w-10 h-5 bg-emerald-500 rounded-full relative">
                      <div className="absolute right-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow" />
                    </div>
                  </div>
                </div>
                <div className="bg-gray-900 p-4 text-white text-xs">
                  <div className="flex items-center gap-2 text-emerald-400">
                    <Check className="w-4 h-4" />
                    Dark mode enabled!
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Workflow State */}
          <div className="mt-4 pt-4 border-t border-white/5">
            <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider mb-3">Workflow</h4>
            <div className="flex flex-wrap gap-1">
              {phases.map((p, i) => (
                <div 
                  key={i}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-all ${
                    i < phase 
                      ? 'bg-emerald-500/20 text-emerald-400' 
                      : i === phase 
                        ? i === 5 
                          ? 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/50'
                          : 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/50' 
                        : 'bg-white/5 text-white/30'
                  }`}
                >
                  <span>{p.icon}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar - No Coders Message */}
      <div className="px-6 py-4 bg-gradient-to-r from-violet-500/10 via-fuchsia-500/10 to-rose-500/10 border-t border-white/10">
        <div className="flex items-center justify-center gap-4 text-sm">
          <span className="text-white/60">No developers needed.</span>
          <span className="text-white font-medium">Just one click to approve.</span>
          <span className="text-violet-400">→</span>
          <span className="text-emerald-400 font-medium">Production ready.</span>
        </div>
      </div>
    </div>
  )
}

// Feature Comparison Table
function FeatureComparisonTable() {
  const features = [
    {
      category: 'Agent & Execution',
      items: [
        { feature: 'Agentic Code Generation', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Multi-file Changes', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Deterministic State Machine', code4u: true, cursor: false, windsurf: false, antigravity: false },
        { feature: 'Contract-Aware Execution', code4u: true, cursor: false, windsurf: false, antigravity: false },
        { feature: 'Human Approval Gates', code4u: true, cursor: 'partial', windsurf: 'partial', antigravity: true },
      ]
    },
    {
      category: 'Codebase Understanding',
      items: [
        { feature: 'Code Embeddings', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Semantic Search', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Full Knowledge Graph', code4u: true, cursor: false, windsurf: false, antigravity: false },
        { feature: 'Dependency Mapping', code4u: true, cursor: 'partial', windsurf: 'partial', antigravity: 'partial' },
        { feature: 'Ownership Boundaries', code4u: true, cursor: false, windsurf: false, antigravity: false },
      ]
    },
    {
      category: 'Enterprise Security',
      items: [
        { feature: 'SOC 2 Type II', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Tenant Isolation', code4u: true, cursor: 'partial', windsurf: true, antigravity: true },
        { feature: 'No-AI Zones', code4u: true, cursor: false, windsurf: false, antigravity: false },
        { feature: 'Immutable Audit Logs', code4u: true, cursor: 'partial', windsurf: true, antigravity: true },
        { feature: 'Self-Hosted Option', code4u: true, cursor: false, windsurf: 'partial', antigravity: false },
      ]
    },
    {
      category: 'IDE Integration',
      items: [
        { feature: 'VS Code Extension', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'JetBrains Plugin', code4u: true, cursor: false, windsurf: true, antigravity: false },
        { feature: 'Autocomplete / Tab', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'CLI Agent', code4u: true, cursor: true, windsurf: false, antigravity: false },
        { feature: 'Browser Agent', code4u: true, cursor: false, windsurf: true, antigravity: true },
      ]
    },
    {
      category: 'Customization',
      items: [
        { feature: 'Rules / Instructions', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Workflows', code4u: true, cursor: 'partial', windsurf: true, antigravity: true },
        { feature: 'MCP Support', code4u: true, cursor: true, windsurf: true, antigravity: true },
        { feature: 'Custom LoRA Adapters', code4u: true, cursor: false, windsurf: false, antigravity: false },
      ]
    },
  ]

  const renderStatus = (status: boolean | string) => {
    if (status === true) return <span className="text-emerald-400 text-lg">✓</span>
    if (status === false) return <span className="text-white/20 text-lg">—</span>
    if (status === 'partial') return <span className="text-amber-400 text-sm">◐</span>
    if (status === 'soon') return <span className="text-blue-400 text-xs font-medium">SOON</span>
    return null
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-white/10">
            <th className="text-left py-4 px-4 text-white/60 font-medium text-sm">Feature</th>
            <th className="text-center py-4 px-4 min-w-[100px]">
              <div className="flex flex-col items-center gap-1">
                <img src="/logo.png" alt="code4u.ai" className="w-6 h-6" />
                <span className="text-emerald-400 font-bold text-xs">code4u.ai</span>
              </div>
            </th>
            <th className="text-center py-4 px-4 min-w-[80px]">
              <span className="text-white/40 text-xs font-medium">Cursor</span>
            </th>
            <th className="text-center py-4 px-4 min-w-[80px]">
              <span className="text-white/40 text-xs font-medium">Windsurf</span>
            </th>
            <th className="text-center py-4 px-4 min-w-[80px]">
              <span className="text-white/40 text-xs font-medium">Antigravity</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {features.map((category, catIdx) => (
            <>
              <tr key={`cat-${catIdx}`} className="bg-white/[0.02]">
                <td colSpan={5} className="py-3 px-4 text-white/80 font-semibold text-sm">{category.category}</td>
              </tr>
              {category.items.map((item, itemIdx) => (
                <tr key={`item-${catIdx}-${itemIdx}`} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                  <td className="py-3 px-4 text-white/60 text-sm">{item.feature}</td>
                  <td className="text-center py-3 px-4 bg-emerald-500/5">{renderStatus(item.code4u)}</td>
                  <td className="text-center py-3 px-4">{renderStatus(item.cursor)}</td>
                  <td className="text-center py-3 px-4">{renderStatus(item.windsurf)}</td>
                  <td className="text-center py-3 px-4">{renderStatus(item.antigravity)}</td>
                </tr>
              ))}
            </>
          ))}
        </tbody>
      </table>
      <div className="mt-6 flex items-center justify-center gap-6 text-xs text-white/40">
        <span className="flex items-center gap-2"><span className="text-emerald-400">✓</span> Full support</span>
        <span className="flex items-center gap-2"><span className="text-amber-400">◐</span> Partial</span>
        <span className="flex items-center gap-2"><span className="text-white/20">—</span> Not available</span>
        <span className="flex items-center gap-2"><span className="text-blue-400 font-medium">SOON</span> Coming soon</span>
      </div>
    </div>
  )
}

// Surface Card
function SurfaceCard({ icon, title, description, status }: { icon: string; title: string; description: string; status: string }) {
  const statusColors: Record<string, string> = {
    'Live': 'bg-emerald-500/20 text-emerald-400',
    'Phase 1': 'bg-emerald-500/20 text-emerald-400',
    'Phase 2': 'bg-blue-500/20 text-blue-400',
    'Phase 3': 'bg-violet-500/20 text-violet-400',
    'Beta': 'bg-amber-500/20 text-amber-400',
  }
  
  return (
    <div className="p-6 rounded-xl bg-white/[0.02] border border-white/10 hover:border-white/20 transition-all group">
      <div className="flex items-start justify-between mb-4">
        <span className="text-3xl">{icon}</span>
        <span className={`text-xs font-medium px-2 py-1 rounded ${statusColors[status] || 'bg-white/10 text-white/40'}`}>
          {status}
        </span>
      </div>
      <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-emerald-400 transition-colors">{title}</h3>
      <p className="text-sm text-white/60">{description}</p>
    </div>
  )
}

// Architecture Card
function ArchitectureCard({ title, description, icon, highlight }: { title: string; description: string; icon: string; highlight: string }) {
  return (
    <div className="p-8 rounded-2xl bg-gradient-to-br from-white/[0.03] to-white/[0.01] border border-white/10 hover:border-violet-500/30 transition-all group">
      <div className="flex items-center gap-4 mb-4">
        <span className="text-4xl">{icon}</span>
        <div>
          <h3 className="text-xl font-bold text-white group-hover:text-violet-400 transition-colors">{title}</h3>
          <span className="text-xs font-medium text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded">{highlight}</span>
        </div>
      </div>
      <p className="text-white/70 leading-relaxed">{description}</p>
    </div>
  )
}

// Roadmap Phase
function RoadmapPhase({ 
  phase, 
  title, 
  timeline, 
  status, 
  goal, 
  features 
}: { 
  phase: string; 
  title: string; 
  timeline: string; 
  status: 'current' | 'upcoming' | 'future' | 'completed'; 
  goal: string; 
  features: string[] 
}) {
  const statusConfig: Record<string, { border: string; bg: string; badge: string; badgeText: string; dot: string }> = {
    current: {
      border: 'border-emerald-500/50',
      bg: 'bg-gradient-to-r from-emerald-500/10 via-transparent to-transparent',
      badge: 'bg-emerald-500/20 text-emerald-400',
      badgeText: 'In Progress',
      dot: 'bg-emerald-500',
    },
    completed: {
      border: 'border-violet-500/50',
      bg: 'bg-gradient-to-r from-violet-500/10 via-transparent to-transparent',
      badge: 'bg-violet-500/20 text-violet-400',
      badgeText: 'Completed',
      dot: 'bg-violet-500',
    },
    upcoming: {
      border: 'border-blue-500/30',
      bg: 'bg-gradient-to-r from-blue-500/5 via-transparent to-transparent',
      badge: 'bg-blue-500/20 text-blue-400',
      badgeText: 'Upcoming',
      dot: 'bg-blue-500',
    },
    future: {
      border: 'border-white/10',
      bg: '',
      badge: 'bg-white/10 text-white/40',
      badgeText: 'Planned',
      dot: 'bg-white/30',
    },
  }
  
  const config = statusConfig[status]
  
  return (
    <div className={`relative p-8 rounded-2xl border ${config.border} ${config.bg} transition-all`}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-full ${config.dot} flex items-center justify-center text-black font-bold text-xl`}>
            {phase}
          </div>
          <div>
            <h3 className="text-2xl font-bold text-white">{title}</h3>
            <p className="text-white/50 text-sm">{timeline}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${config.badge}`}>{config.badgeText}</span>
          <span className="text-white/60 text-sm">🎯 {goal}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {features.map((feature, i) => (
          <div 
            key={i}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-sm text-white/70"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`}></span>
            <span className="truncate">{feature}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// File Icon helper
function FileIcon({ filename }: { filename: string }) {
  const ext = filename.split('.').pop()
  const colors: Record<string, string> = {
    py: 'text-blue-400',
    ts: 'text-blue-400',
    tsx: 'text-blue-400',
    js: 'text-yellow-400',
    json: 'text-amber-400',
  }
  return (
    <div className={`w-4 h-4 ${colors[ext || ''] || 'text-white/40'}`}>
      <svg viewBox="0 0 16 16" fill="currentColor">
        <path d="M3.5 0A1.5 1.5 0 0 0 2 1.5v13A1.5 1.5 0 0 0 3.5 16h9a1.5 1.5 0 0 0 1.5-1.5V4.5L10.5 0h-7zM10 4V1l3 3h-3z"/>
      </svg>
    </div>
  )
}

// Stat Block
function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="text-5xl font-bold bg-gradient-to-r from-white to-white/80 bg-clip-text text-transparent mb-2">{value}</p>
      <p className="text-white/70">{label}</p>
    </div>
  )
}

// Testimonial Card
function TestimonialCard({ quote, author, role, company }: { quote: string; author: string; role: string; company: string }) {
  return (
    <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-colors backdrop-blur-sm">
      <div className="flex gap-1 mb-6">
        {[...Array(5)].map((_, i) => (
          <svg key={i} className="w-5 h-5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        ))}
      </div>
      <p className="text-white text-lg mb-6">"{quote}"</p>
      <div>
        <p className="font-semibold text-white">{author}</p>
        <p className="text-white/70 text-sm">{role} • {company}</p>
      </div>
    </div>
  )
}

// Compliance Tab
function ComplianceTab({ compliance }: { compliance: ComplianceData | null }) {
  if (!compliance) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-16">
      <div className="flex justify-between items-start mb-12">
        <div>
          <h2 className="text-4xl font-bold text-white mb-2">Compliance Dashboard</h2>
          <p className="text-white/70">Real-time SOC 2 Type II & ISO 27001 control monitoring</p>
        </div>
        <div className={`flex items-center gap-3 px-5 py-3 rounded-full ${
          compliance.summary.compliance_rate === 100 
            ? 'bg-emerald-500/10 border border-emerald-500/20' 
            : 'bg-amber-500/10 border border-amber-500/20'
        }`}>
          <span className={`w-3 h-3 rounded-full ${compliance.summary.compliance_rate === 100 ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
          <span className={`font-semibold ${compliance.summary.compliance_rate === 100 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {compliance.summary.compliance_rate}% Compliant
          </span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-12">
        <SummaryCard value={compliance.summary.total} label="Total Controls" />
        <SummaryCard value={compliance.summary.passing} label="Passing" color="emerald" />
        <SummaryCard value={compliance.summary.failing} label="Failing" color="red" />
        <SummaryCard value={0} label="Warnings" color="amber" />
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-white mb-4">Control Status</h3>
        {compliance.results.map(control => (
          <ControlCard key={control.control_id} control={control} />
        ))}
      </div>
    </div>
  )
}

// Pricing Tab
function PricingTab({ tiers, onGetStarted }: { tiers: Record<string, PricingTier> | null; onGetStarted: () => void }) {
  if (!tiers) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-16">
      <div className="text-center mb-16">
        <span className="inline-block px-4 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium mb-6">Pricing</span>
        <h2 className="text-5xl font-bold text-white mb-4">Pay for outcomes, not tokens</h2>
        <p className="text-xl text-white/70">Predictable pricing based on the value you create</p>
      </div>

      <div className="grid md:grid-cols-3 gap-8 mb-16">
        {Object.entries(tiers).map(([name, tier]) => (
          <TierCard key={name} name={name} tier={tier} onGetStarted={onGetStarted} />
        ))}
      </div>

      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-10 text-center">
        <h3 className="text-2xl font-bold text-white mb-4">Enterprise needs?</h3>
        <p className="text-white/70 mb-6 max-w-xl mx-auto">Custom deployments, dedicated infrastructure, advanced compliance, and white-glove onboarding.</p>
        <button 
          onClick={onGetStarted}
          className="px-8 py-4 border border-white/20 rounded-full font-semibold hover:bg-white/5 transition-colors"
        >
          Talk to Sales
        </button>
      </div>
    </div>
  )
}

// Shared Components
function SummaryCard({ value, label, color }: { value: number; label: string; color?: string }) {
  const textColors: Record<string, string> = { emerald: 'text-emerald-400', red: 'text-red-400', amber: 'text-amber-400' }
  return (
    <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
      <p className={`text-4xl font-bold ${color ? textColors[color] : 'text-white'}`}>{value}</p>
      <p className="text-white/70 mt-1">{label}</p>
    </div>
  )
}

function ControlCard({ control }: { control: ComplianceResult }) {
  const colors: Record<string, { bg: string; text: string; dot: string }> = {
    passing: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    failing: { bg: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-400' },
    warning: { bg: 'bg-amber-500/10', text: 'text-amber-400', dot: 'bg-amber-400' },
  }
  const style = colors[control.status] || colors.passing

  return (
    <div className="bg-white/[0.02] border border-white/10 rounded-xl p-5 hover:border-white/20 transition-colors backdrop-blur-sm">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <code className="text-xs text-white/60 bg-white/5 px-2 py-1 rounded">{control.control_id}</code>
            <span className="text-xs text-white/50">{control.framework}</span>
          </div>
          <h4 className="text-lg font-medium text-white mb-1">{control.control_name}</h4>
          <p className="text-white/60 text-sm">{control.details}</p>
        </div>
        <span className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {control.status.toUpperCase()}
        </span>
      </div>
    </div>
  )
}

function TierCard({ name, tier, onGetStarted }: { name: string; tier: PricingTier; onGetStarted: () => void }) {
  const isPopular = name === 'team'
  const isEnterprise = name === 'enterprise'

  return (
    <div className={`relative rounded-2xl p-8 ${
      isPopular 
        ? 'bg-gradient-to-b from-emerald-500/10 to-transparent border-2 border-emerald-500/30' 
        : 'bg-white/[0.02] border border-white/10'
    }`}>
      {isPopular && (
        <span className="absolute -top-4 left-1/2 -translate-x-1/2 bg-emerald-500 text-black px-4 py-1.5 rounded-full text-xs font-bold">
          MOST POPULAR
        </span>
      )}
      <h4 className="text-2xl font-bold text-white capitalize mb-2">{name}</h4>
      <p className="text-white/60 text-sm mb-6">
        {name === 'developer' && 'Perfect for individual devs'}
        {name === 'team' && 'For growing engineering teams'}
        {name === 'enterprise' && 'For large-scale organizations'}
      </p>
      <div className="mb-6">
        <span className="text-5xl font-bold text-white">${tier.pricing.base_price_usd}</span>
        <span className="text-white/60">/month</span>
        {tier.pricing.per_seat_usd > 0 && (
          <p className="text-white/60 text-sm mt-1">+ ${tier.pricing.per_seat_usd}/additional seat</p>
        )}
      </div>
      <ul className="space-y-3 mb-8">
        <TierFeature text={`${tier.limits.refactors_per_month.toLocaleString()} refactors/month`} />
        <TierFeature text={`${tier.limits.included_seats} included seat${tier.limits.included_seats > 1 ? 's' : ''}`} />
        {tier.limits.cross_repo_allowed && <TierFeature text="Cross-repo changes" />}
        {tier.features.contract_validation && <TierFeature text="Contract validation" />}
        {tier.features.audit_logs && <TierFeature text="Audit logs" />}
        {tier.features.dedicated_gpus && <TierFeature text="Dedicated GPUs" />}
        {tier.features.tenant_isolation && <TierFeature text="Tenant isolation" />}
      </ul>
      <button 
        onClick={onGetStarted}
        className={`w-full py-4 rounded-xl font-semibold transition-all ${
          isPopular 
            ? 'bg-emerald-500 text-black hover:bg-emerald-400' 
            : isEnterprise 
              ? 'bg-white text-black hover:bg-white/90'
              : 'border border-white/20 text-white hover:bg-white/5'
        }`}
      >
        {isEnterprise ? 'Contact Sales' : 'Get Started'}
      </button>
    </div>
  )
}

function TierFeature({ text }: { text: string }) {
  return (
    <li className="flex items-center gap-3 text-white/70">
      <Check className="w-5 h-5 text-emerald-400 flex-shrink-0" />
      {text}
    </li>
  )
}

// Footer
function FooterColumn({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <h5 className="font-semibold text-white mb-4">{title}</h5>
      <ul className="space-y-2">
        {links.map(link => (
          <li key={link}>
            <a href="#" className="text-sm text-white/60 hover:text-white transition-colors">{link}</a>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SocialIcon({ name }: { name: string }) {
  return (
    <a href="#" className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors">
      <span className="text-white/60">{name[0].toUpperCase()}</span>
    </a>
  )
}

// Icons
function Check({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function ShieldCheck({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  )
}

function KnowledgeGraphIcon() {
  return (
    <svg className="w-7 h-7 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
    </svg>
  )
}

function StateMachineIcon() {
  return (
    <svg className="w-7 h-7 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
    </svg>
  )
}

function ContractIcon() {
  return (
    <svg className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg className="w-7 h-7 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  )
}

// RIL Pipeline Demo
function RILPipelineDemo() {
  const [phase, setPhase] = useState(0)
  
  const phases = [
    { state: 'MEETING', label: 'Meeting in progress...', icon: '🎙️', color: 'rose' },
    { state: 'TRANSCRIBING', label: 'Transcribing...', icon: '📝', color: 'fuchsia' },
    { state: 'CLASSIFYING', label: 'Classifying segments...', icon: '🧠', color: 'violet' },
    { state: 'EXTRACTING', label: 'Extracting requirements...', icon: '📋', color: 'blue' },
    { state: 'GRAPH', label: 'Adding to Knowledge Graph...', icon: '🔗', color: 'cyan' },
    { state: 'PLANNING', label: 'Generating plan...', icon: '📐', color: 'emerald' },
    { state: 'AWAITING', label: 'Awaiting approval...', icon: '👀', color: 'amber' },
    { state: 'EXECUTING', label: 'Agent implementing...', icon: '⚡', color: 'blue' },
    { state: 'DEPLOYED', label: 'Deployed to production!', icon: '🚀', color: 'emerald' },
  ]

  const transcript = [
    { speaker: 'PM', text: 'We need SSO with Okta before Q4 and it has to be SOC2 compliant.' },
    { speaker: 'Eng', text: 'Should we use SAML or OIDC?' },
    { speaker: 'PM', text: "Let's go with OIDC, it's more modern." },
    { speaker: 'Eng', text: "We'll need to update the auth service and add Okta as an identity provider." },
  ]

  const extractedReq = {
    id: 'REQ-401',
    title: 'Implement Okta SSO',
    type: 'functional',
    priority: 'high',
    deadline: 'Q4 2025',
    systems: ['Auth Service', 'Frontend', 'Backend'],
    constraints: ['SOC2', 'OIDC'],
    source: 'Zoom Meeting - Product Sync',
  }

  useEffect(() => {
    const durations = [3000, 2000, 2500, 2500, 2000, 2000, 3000, 3000, 4000]
    if (phase < phases.length - 1) {
      const timer = setTimeout(() => setPhase(p => p + 1), durations[phase])
      return () => clearTimeout(timer)
    } else {
      const timer = setTimeout(() => setPhase(0), 5000)
      return () => clearTimeout(timer)
    }
  }, [phase])

  const progress = (phase / (phases.length - 1)) * 100
  const currentPhase = phases[phase]

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#0a0a0f] shadow-2xl shadow-black/50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#12121a]">
        <div className="flex items-center gap-4">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
            <div className="w-3 h-3 rounded-full bg-[#27ca40]" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-rose-400">🎙️</span>
            <span className="text-white/60 text-sm font-medium">Requirements Intelligence Layer</span>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-500/20 text-rose-400">
          {phase > 0 && phase < phases.length - 1 && (
            <div className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
          )}
          <span>{currentPhase.state}</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-white/5">
        <div 
          className="h-full bg-gradient-to-r from-rose-500 via-fuchsia-500 via-violet-500 to-emerald-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="grid lg:grid-cols-2 min-h-[450px]">
        {/* Left - Meeting/Transcript */}
        <div className="p-6 border-r border-white/5">
          {/* Meeting Header */}
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-rose-500/20 flex items-center justify-center">
              <span className="text-xl">🎥</span>
            </div>
            <div>
              <p className="text-white font-medium">Product Sync - Q4 Planning</p>
              <p className="text-white/40 text-xs">Zoom Meeting • 4 participants</p>
            </div>
            {phase === 0 && (
              <span className="ml-auto flex items-center gap-2 px-2 py-1 rounded-full bg-rose-500/20 text-rose-400 text-xs">
                <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
                Live
              </span>
            )}
          </div>

          {/* Transcript */}
          <div className="space-y-3 mb-6">
            <p className="text-white/40 text-xs uppercase tracking-wider">Transcript</p>
            {transcript.map((line, i) => (
              <div 
                key={i} 
                className={`flex gap-3 p-3 rounded-lg transition-all ${
                  phase >= 1 ? 'bg-white/[0.02]' : 'bg-white/[0.01]'
                } ${phase === 2 && i === 0 ? 'ring-1 ring-fuchsia-500/50' : ''}`}
              >
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  line.speaker === 'PM' ? 'bg-blue-500/20 text-blue-400' : 'bg-emerald-500/20 text-emerald-400'
                }`}>{line.speaker}</span>
                <p className="text-white/70 text-sm flex-1">{line.text}</p>
                {phase >= 2 && i === 0 && (
                  <span className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded">REQUIREMENT</span>
                )}
              </div>
            ))}
          </div>

          {/* Classification Results */}
          {phase >= 2 && (
            <div className="animate-fade-in space-y-2">
              <p className="text-white/40 text-xs uppercase tracking-wider">Classified Segments</p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 rounded bg-violet-500/20 text-violet-400 text-xs">2 Requirements</span>
                <span className="px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-xs">1 Decision</span>
                <span className="px-2 py-1 rounded bg-amber-500/20 text-amber-400 text-xs">0 Risks</span>
                <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs">1 Action Item</span>
              </div>
            </div>
          )}
        </div>

        {/* Right - Extracted Requirement & Execution */}
        <div className="p-6 bg-[#0a0a0f]">
          {phase >= 3 && (
            <div className="animate-fade-in">
              <p className="text-white/40 text-xs uppercase tracking-wider mb-4">Structured Requirement</p>
              
              {/* Requirement Card */}
              <div className="bg-gradient-to-br from-violet-500/10 to-blue-500/10 rounded-xl p-5 border border-violet-500/30 mb-6">
                <div className="flex items-start justify-between mb-3">
                  <span className="px-2 py-0.5 bg-violet-500/30 text-violet-400 text-xs font-bold rounded">{extractedReq.id}</span>
                  <span className="px-2 py-0.5 bg-rose-500/20 text-rose-400 text-xs rounded">{extractedReq.priority}</span>
                </div>
                <h4 className="text-white font-bold text-lg mb-2">{extractedReq.title}</h4>
                
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-white/40 mb-1">Systems</p>
                    <div className="flex flex-wrap gap-1">
                      {extractedReq.systems.map((s, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-white/5 text-white/60 rounded">{s}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-white/40 mb-1">Constraints</p>
                    <div className="flex flex-wrap gap-1">
                      {extractedReq.constraints.map((c, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">{c}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-white/40 mb-1">Deadline</p>
                    <span className="text-white/70">{extractedReq.deadline}</span>
                  </div>
                  <div>
                    <p className="text-white/40 mb-1">Source</p>
                    <span className="text-cyan-400">{extractedReq.source}</span>
                  </div>
                </div>
              </div>

              {/* Execution Progress */}
              {phase >= 5 && (
                <div className="space-y-3 animate-fade-in">
                  <p className="text-white/40 text-xs uppercase tracking-wider">Execution Status</p>
                  
                  {phase >= 5 && (
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span className="text-white/70">Technical plan generated</span>
                      <span className="ml-auto text-xs text-white/40">3 tasks</span>
                    </div>
                  )}
                  
                  {phase >= 6 && (
                    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 animate-fade-in">
                      <div className="flex items-center gap-2 text-amber-400 text-sm font-medium mb-1">
                        <span>👀</span>
                        <span>Awaiting Approval</span>
                      </div>
                      <p className="text-amber-400/60 text-xs">Review the plan in Slack or dashboard</p>
                    </div>
                  )}
                  
                  {phase >= 7 && (
                    <div className="flex items-center gap-2 text-sm animate-fade-in">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span className="text-emerald-400 font-medium">Approved</span>
                      <span className="ml-auto text-xs text-white/40">by Sarah Chen</span>
                    </div>
                  )}
                  
                  {phase >= 7 && phase < 8 && (
                    <div className="flex items-center gap-2 text-sm animate-fade-in">
                      <div className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
                      <span className="text-blue-400">Agent implementing changes...</span>
                    </div>
                  )}
                  
                  {phase >= 8 && (
                    <div className="p-4 rounded-lg bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 animate-fade-in">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-emerald-500/30 flex items-center justify-center">
                          <span className="text-xl">🚀</span>
                        </div>
                        <div>
                          <p className="text-emerald-400 font-bold">Deployed to Production!</p>
                          <p className="text-emerald-400/60 text-xs">PR #892 merged • 3 files changed</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {phase < 3 && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                  <span className="text-3xl">{currentPhase.icon}</span>
                </div>
                <p className="text-white/40">{currentPhase.label}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="px-6 py-4 bg-[#12121a] border-t border-white/10">
        <div className="flex items-center justify-between">
          {phases.map((p, i) => (
            <div 
              key={i}
              className={`flex flex-col items-center transition-all ${
                i === phase ? 'scale-110' : ''
              }`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                i < phase 
                  ? 'bg-emerald-500/20 text-emerald-400' 
                  : i === phase 
                    ? `bg-${p.color}-500/20 text-${p.color}-400 ring-2 ring-${p.color}-500/50`
                    : 'bg-white/5 text-white/30'
              }`}>
                {i < phase ? <Check className="w-4 h-4" /> : p.icon}
              </div>
              <span className={`text-[10px] mt-1 ${i <= phase ? 'text-white/60' : 'text-white/20'}`}>
                {p.state.slice(0, 4)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// RIL Feature Card
function RILFeatureCard({ icon, title, description, platforms, tags, metrics }: { 
  icon: string; 
  title: string; 
  description: string; 
  platforms?: string[];
  tags?: string[];
  metrics?: string[];
}) {
  return (
    <div className="p-6 rounded-xl bg-gradient-to-br from-white/[0.03] to-transparent border border-white/10 hover:border-rose-500/30 transition-all group">
      <span className="text-4xl mb-4 block">{icon}</span>
      <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-rose-400 transition-colors">{title}</h3>
      <p className="text-white/60 mb-4 text-sm">{description}</p>
      {platforms && (
        <div className="flex flex-wrap gap-2">
          {platforms.map((p, i) => (
            <span key={i} className="px-2 py-1 bg-white/5 text-white/50 text-xs rounded">{p}</span>
          ))}
        </div>
      )}
      {tags && (
        <div className="flex flex-wrap gap-2">
          {tags.map((t, i) => (
            <span key={i} className="px-2 py-1 bg-violet-500/20 text-violet-400 text-xs rounded">{t}</span>
          ))}
        </div>
      )}
      {metrics && (
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-emerald-400">{metrics[0]}</span>
          <span className="text-white/50 text-sm">{metrics[1]}</span>
        </div>
      )}
    </div>
  )
}

// Otter Comparison
function OtterComparison({ feature, otter, code4u }: { feature: string; otter: boolean; code4u: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5">
      <span className="text-white/70 text-sm">{feature}</span>
      <div className="flex items-center gap-8">
        <span className={otter ? 'text-white/40' : 'text-white/20'}>
          {otter ? '✓' : '—'}
        </span>
        <span className={code4u ? 'text-emerald-400' : 'text-white/20'}>
          {code4u ? '✓' : '—'}
        </span>
      </div>
    </div>
  )
}

// Integration Grid
function IntegrationGrid() {
  const categories = [
    {
      title: 'Communication',
      icon: '💬',
      items: [
        { name: 'Slack', icon: '💬', status: 'live' },
        { name: 'Microsoft Teams', icon: '👥', status: 'live' },
        { name: 'Discord', icon: '🎮', status: 'beta' },
      ]
    },
    {
      title: 'Meetings',
      icon: '🎥',
      items: [
        { name: 'Zoom', icon: '📹', status: 'live' },
        { name: 'Google Meet', icon: '🎦', status: 'live' },
        { name: 'Webex', icon: '📞', status: 'beta' },
      ]
    },
    {
      title: 'Project Management',
      icon: '📋',
      items: [
        { name: 'Jira', icon: '📊', status: 'live' },
        { name: 'Asana', icon: '✅', status: 'live' },
        { name: 'Linear', icon: '⚡', status: 'live' },
        { name: 'Monday.com', icon: '📅', status: 'beta' },
        { name: 'ClickUp', icon: '🎯', status: 'beta' },
        { name: 'Trello', icon: '📌', status: 'beta' },
      ]
    },
    {
      title: 'ITSM',
      icon: '🎫',
      items: [
        { name: 'ServiceNow', icon: '🔧', status: 'live' },
        { name: 'Zendesk', icon: '🎧', status: 'live' },
        { name: 'Freshservice', icon: '🌿', status: 'beta' },
      ]
    },
    {
      title: 'Documentation',
      icon: '📝',
      items: [
        { name: 'Notion', icon: '📓', status: 'live' },
        { name: 'Confluence', icon: '📚', status: 'beta' },
      ]
    },
    {
      title: 'Design',
      icon: '🎨',
      items: [
        { name: 'Figma', icon: '🖼️', status: 'beta' },
        { name: 'Miro', icon: '🖍️', status: 'beta' },
      ]
    },
  ]

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      {categories.map((cat, i) => (
        <div key={i} className="p-6 rounded-xl bg-white/[0.02] border border-white/10 hover:border-blue-500/30 transition-all">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">{cat.icon}</span>
            <h3 className="text-lg font-semibold text-white">{cat.title}</h3>
          </div>
          <div className="space-y-2">
            {cat.items.map((item, j) => (
              <div key={j} className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] transition-colors">
                <div className="flex items-center gap-2">
                  <span>{item.icon}</span>
                  <span className="text-white/70 text-sm">{item.name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  item.status === 'live' 
                    ? 'bg-emerald-500/20 text-emerald-400' 
                    : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {item.status === 'live' ? 'Live' : 'Beta'}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default App
