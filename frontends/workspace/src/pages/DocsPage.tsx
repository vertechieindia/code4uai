import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { 
  BookOpen,
  Search,
  ChevronRight,
  Code2,
  Brain,
  GitBranch,
  Terminal,
  Settings,
  Zap,
  ExternalLink
} from 'lucide-react'

export default function DocsPage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  const sections = [
    {
      title: 'Getting Started',
      icon: BookOpen,
      articles: [
        { title: 'Quick Start Guide', path: '#' },
        { title: 'Installation', path: '#' },
        { title: 'First Project', path: '#' },
      ]
    },
    {
      title: 'IDE Features',
      icon: Code2,
      articles: [
        { title: 'Code Editor', path: '#' },
        { title: 'Terminal Integration', path: '#' },
        { title: 'Git Support', path: '#' },
      ]
    },
    {
      title: 'AI Agent',
      icon: Brain,
      articles: [
        { title: 'Agent Overview', path: '#' },
        { title: 'Writing Instructions', path: '#' },
        { title: 'Task Management', path: '#' },
      ]
    },
    {
      title: 'Integrations',
      icon: GitBranch,
      articles: [
        { title: 'GitHub', path: '#' },
        { title: 'GitLab', path: '#' },
        { title: 'Bitbucket', path: '#' },
      ]
    },
    {
      title: 'API Reference',
      icon: Terminal,
      articles: [
        { title: 'REST API', path: '#' },
        { title: 'WebSocket API', path: '#' },
        { title: 'Authentication', path: '#' },
      ]
    },
    {
      title: 'Configuration',
      icon: Settings,
      articles: [
        { title: 'Project Settings', path: '#' },
        { title: 'Team Settings', path: '#' },
        { title: 'Agent Configuration', path: '#' },
      ]
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Documentation</h1>
          <p className="text-white/50">Everything you need to know about code4u.ai</p>
        </div>
        <a
          href="https://docs.code4u.ai"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 bg-white/10 border border-white/20 rounded-lg font-medium hover:bg-white/20 transition-colors"
        >
          Full Docs
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-white/40" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search documentation..."
          className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-lg focus:outline-none focus:border-emerald-500/50"
        />
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: Zap, label: 'Quick Start', desc: '5 min read', path: '#' },
          { icon: Brain, label: 'AI Agent Guide', desc: '10 min read', path: '/agent' },
          { icon: Code2, label: 'IDE Tutorial', desc: '7 min read', path: '/ide' },
          { icon: Terminal, label: 'API Reference', desc: 'Full docs', path: '#' },
        ].map((link) => (
          <button
            key={link.label}
            onClick={() => link.path.startsWith('/') ? navigate(link.path) : null}
            className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-left group"
          >
            <link.icon className="w-6 h-6 text-emerald-400 mb-2" />
            <h3 className="font-medium group-hover:text-emerald-400 transition-colors">{link.label}</h3>
            <p className="text-sm text-white/50">{link.desc}</p>
          </button>
        ))}
      </div>

      {/* Documentation Sections */}
      <div className="grid grid-cols-3 gap-6">
        {sections.map((section) => (
          <div key={section.title} className="bg-white/5 border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                <section.icon className="w-5 h-5 text-emerald-400" />
              </div>
              <h2 className="font-semibold">{section.title}</h2>
            </div>
            <div className="space-y-2">
              {section.articles.map((article) => (
                <button
                  key={article.title}
                  className="w-full flex items-center justify-between p-2 rounded hover:bg-white/5 text-left group"
                >
                  <span className="text-white/70 group-hover:text-white transition-colors">
                    {article.title}
                  </span>
                  <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-white/60" />
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

