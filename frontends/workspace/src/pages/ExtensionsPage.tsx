import { useNavigate } from 'react-router-dom'
import { 
  ArrowLeft,
  Code2,
  Sparkles,
  Terminal,
  Brain,
  Zap,
  GitBranch,
  CheckCircle2
} from 'lucide-react'

export default function ExtensionsPage() {
  const navigate = useNavigate()

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate('/')}
          className="p-2 hover:bg-white/10 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">code4u.ai IDE</h1>
          <p className="text-white/50">Your complete AI-powered development environment</p>
        </div>
      </div>

      {/* Main IDE Card */}
      <div className="bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 rounded-xl p-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-2xl flex items-center justify-center">
              <Code2 className="w-10 h-10 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold mb-2">Open code4u.ai IDE</h2>
              <p className="text-white/60 max-w-md">
                Full-featured IDE with code editor, terminal, AI assistant, and git integration. 
                No download required - code directly in your browser.
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate('/ide')}
            className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl font-semibold text-lg hover:shadow-lg hover:shadow-emerald-500/25 transition-all hover:-translate-y-0.5"
          >
            <Sparkles className="w-5 h-5" />
            Launch IDE
          </button>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-2 gap-4">
        {[
          { icon: Code2, title: 'Code Editor', desc: 'Syntax highlighting, multi-file tabs, auto-save' },
          { icon: Terminal, title: 'Integrated Terminal', desc: 'Run commands, npm, git directly in browser' },
          { icon: Brain, title: 'AI Assistant', desc: 'Chat with AI to write, fix, and explain code' },
          { icon: GitBranch, title: 'Git Integration', desc: 'Commit, push, and manage branches' },
          { icon: Zap, title: 'Quick Actions', desc: 'One-click refactor, test generation, docs' },
          { icon: Sparkles, title: 'AI Completions', desc: 'Smart code suggestions as you type' },
        ].map((feature) => (
          <div key={feature.title} className="bg-white/5 border border-white/10 rounded-xl p-5">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <feature.icon className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">{feature.title}</h3>
                <p className="text-sm text-white/50">{feature.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Benefits */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <h3 className="font-semibold mb-4">Why use code4u.ai IDE?</h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            'No installation required',
            'Works on any device',
            'Cloud-synced projects',
            'Built-in AI assistant',
            'Real-time collaboration',
            'Automatic backups',
          ].map((benefit) => (
            <div key={benefit} className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-white/70">{benefit}</span>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="text-center py-6">
        <button
          onClick={() => navigate('/ide')}
          className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl font-semibold text-lg hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
        >
          <Code2 className="w-5 h-5" />
          Start Coding Now
        </button>
        <p className="text-sm text-white/40 mt-3">Free to use • No credit card required</p>
      </div>
    </div>
  )
}
