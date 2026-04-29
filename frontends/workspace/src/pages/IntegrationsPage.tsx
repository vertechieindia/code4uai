import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { 
  ArrowLeft,
  Search,
  CheckCircle2,
  ExternalLink,
  Settings,
  Zap
} from 'lucide-react'

interface Integration {
  id: string
  name: string
  category: string
  description: string
  logo: string
  bgColor: string
  connected: boolean
  popular?: boolean
}

export default function IntegrationsPage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  const categories = [
    { id: 'all', label: 'All' },
    { id: 'ide', label: 'IDE Extensions' },
    { id: 'git', label: 'Version Control' },
    { id: 'communication', label: 'Communication' },
    { id: 'project', label: 'Project Management' },
    { id: 'cicd', label: 'CI/CD & Deployment' },
    { id: 'database', label: 'Databases' },
    { id: 'monitoring', label: 'Monitoring' },
    { id: 'ai', label: 'AI & ML' },
  ]

  const integrations: Integration[] = [
    // Version Control
    { id: 'github', name: 'GitHub', category: 'git', description: 'Connect repositories, sync issues, automate PRs', logo: '/logos/github.svg', bgColor: '#181717', connected: true, popular: true },
    { id: 'gitlab', name: 'GitLab', category: 'git', description: 'GitLab repositories and CI/CD pipelines', logo: '/logos/gitlab.svg', bgColor: '#FC6D26', connected: false, popular: true },
    { id: 'bitbucket', name: 'Bitbucket', category: 'git', description: 'Atlassian Bitbucket repositories', logo: '/logos/bitbucket.svg', bgColor: '#0052CC', connected: false },

    // Communication
    { id: 'slack', name: 'Slack', category: 'communication', description: 'Get notifications, run commands from Slack', logo: '/logos/slack.svg', bgColor: '#4A154B', connected: false, popular: true },
    { id: 'discord', name: 'Discord', category: 'communication', description: 'Discord bot for team notifications', logo: '/logos/discord.svg', bgColor: '#5865F2', connected: false },
    { id: 'teams', name: 'Microsoft Teams', category: 'communication', description: 'Teams integration for enterprises', logo: '/logos/microsoftteams.svg', bgColor: '#6264A7', connected: false },
    { id: 'email', name: 'Email', category: 'communication', description: 'Email notifications and digests', logo: '/logos/gmail.svg', bgColor: '#EA4335', connected: true },

    // Project Management
    { id: 'jira', name: 'Jira', category: 'project', description: 'Sync issues, update tickets automatically', logo: '/logos/jira.svg', bgColor: '#0052CC', connected: false, popular: true },
    { id: 'linear', name: 'Linear', category: 'project', description: 'Modern issue tracking integration', logo: '/logos/linear.svg', bgColor: '#5E6AD2', connected: false, popular: true },
    { id: 'notion', name: 'Notion', category: 'project', description: 'Sync docs, create pages from code', logo: '/logos/notion.svg', bgColor: '#000000', connected: false },
    { id: 'asana', name: 'Asana', category: 'project', description: 'Task management and workflows', logo: '/logos/asana.svg', bgColor: '#F06A6A', connected: false },
    { id: 'trello', name: 'Trello', category: 'project', description: 'Kanban boards and cards', logo: '/logos/trello.svg', bgColor: '#0052CC', connected: false },

    // CI/CD & Deployment
    { id: 'vercel', name: 'Vercel', category: 'cicd', description: 'Deploy frontend apps instantly', logo: '/logos/vercel.svg', bgColor: '#000000', connected: false, popular: true },
    { id: 'netlify', name: 'Netlify', category: 'cicd', description: 'Deploy and host web projects', logo: '/logos/netlify.svg', bgColor: '#00C7B7', connected: false },
    { id: 'aws', name: 'AWS', category: 'cicd', description: 'Amazon Web Services integration', logo: '/logos/amazonaws.svg', bgColor: '#232F3E', connected: false, popular: true },
    { id: 'gcp', name: 'Google Cloud', category: 'cicd', description: 'Google Cloud Platform services', logo: '/logos/googlecloud.svg', bgColor: '#4285F4', connected: false },
    { id: 'azure', name: 'Azure', category: 'cicd', description: 'Microsoft Azure cloud services', logo: '/logos/microsoftazure.svg', bgColor: '#0078D4', connected: false },
    { id: 'docker', name: 'Docker Hub', category: 'cicd', description: 'Container registry and builds', logo: '/logos/docker.svg', bgColor: '#2496ED', connected: false },

    // Databases
    { id: 'supabase', name: 'Supabase', category: 'database', description: 'Open source Firebase alternative', logo: '/logos/supabase.svg', bgColor: '#3FCF8E', connected: false, popular: true },
    { id: 'firebase', name: 'Firebase', category: 'database', description: 'Google Firebase backend services', logo: '/logos/firebase.svg', bgColor: '#DD2C00', connected: false },
    { id: 'planetscale', name: 'PlanetScale', category: 'database', description: 'Serverless MySQL platform', logo: '/logos/planetscale.svg', bgColor: '#000000', connected: false },
    { id: 'mongodb', name: 'MongoDB Atlas', category: 'database', description: 'Cloud MongoDB database', logo: '/logos/mongodb.svg', bgColor: '#47A248', connected: false },
    { id: 'postgres', name: 'PostgreSQL', category: 'database', description: 'Connect to Postgres databases', logo: '/logos/postgresql.svg', bgColor: '#4169E1', connected: false },

    // Monitoring
    { id: 'sentry', name: 'Sentry', category: 'monitoring', description: 'Error tracking and monitoring', logo: '/logos/sentry.svg', bgColor: '#362D59', connected: false, popular: true },
    { id: 'datadog', name: 'Datadog', category: 'monitoring', description: 'APM and infrastructure monitoring', logo: '/logos/datadog.svg', bgColor: '#632CA6', connected: false },
    { id: 'logrocket', name: 'LogRocket', category: 'monitoring', description: 'Session replay and analytics', logo: '/logos/logrocket.svg', bgColor: '#764ABC', connected: false },

    // AI & ML
    { id: 'openai', name: 'OpenAI', category: 'ai', description: 'GPT models and embeddings', logo: '/logos/openai.svg', bgColor: '#412991', connected: true, popular: true },
    { id: 'anthropic', name: 'Anthropic', category: 'ai', description: 'Claude AI models', logo: '/logos/anthropic.svg', bgColor: '#191919', connected: false },
    { id: 'huggingface', name: 'Hugging Face', category: 'ai', description: 'ML models and datasets', logo: '/logos/huggingface.svg', bgColor: '#FF9D00', connected: false },

    // IDE
    { id: 'vscode', name: 'VS Code Extension', category: 'ide', description: 'AI-powered completions and refactoring in VS Code', logo: 'vscode', bgColor: '#007ACC', connected: false, popular: true },
  ]

  const filteredIntegrations = integrations.filter(i => {
    const matchesSearch = i.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         i.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = selectedCategory === 'all' || i.category === selectedCategory
    return matchesSearch && matchesCategory
  })

  const connectedCount = integrations.filter(i => i.connected).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/')}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold">Integrations</h1>
            <p className="text-white/50">Connect your favorite tools to automate workflows</p>
          </div>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
          <CheckCircle2 className="w-4 h-4" />
          <span className="font-medium">{connectedCount} Connected</span>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search integrations..."
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-emerald-500/50"
          />
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setSelectedCategory(cat.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              selectedCategory === cat.id
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                : 'bg-white/5 text-white/60 border border-white/10 hover:bg-white/10'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Integrations Grid */}
      <div className="grid grid-cols-3 gap-4">
        {filteredIntegrations.map((integration) => (
          <div
            key={integration.id}
            className="bg-white/5 border border-white/10 rounded-xl p-5 hover:bg-white/10 transition-all group"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                {integration.logo === 'vscode' ? (
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: integration.bgColor }}>
                    <svg viewBox="0 0 24 24" className="w-7 h-7" fill="white">
                      <path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352z"/>
                    </svg>
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center p-2.5" style={{ background: integration.bgColor }}>
                    <img
                      src={integration.logo}
                      alt={integration.name}
                      className="w-full h-full object-contain brightness-0 invert"
                    />
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{integration.name}</h3>
                    {integration.popular && (
                      <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-xs">Popular</span>
                    )}
                  </div>
                  <p className="text-xs text-white/40">{categories.find(c => c.id === integration.category)?.label}</p>
                </div>
              </div>
            </div>
            <p className="text-sm text-white/60 mb-4">{integration.description}</p>
            <div className="flex items-center justify-between">
              {integration.connected ? (
                <div className="flex items-center gap-2 text-emerald-400 text-sm">
                  <CheckCircle2 className="w-4 h-4" />
                  Connected
                </div>
              ) : (
                <button className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded-lg text-sm font-medium hover:bg-emerald-500/30 transition-colors">
                  <Zap className="w-4 h-4" />
                  Connect
                </button>
              )}
              <button className="p-2 text-white/40 hover:text-white hover:bg-white/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                <Settings className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Request Integration */}
      <div className="bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold mb-1">Need a different integration?</h3>
            <p className="text-sm text-white/60">Request a new integration or use our API to build your own</p>
          </div>
          <div className="flex gap-3">
            <button className="px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-sm font-medium hover:bg-white/20 transition-colors">
              Request Integration
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-sm font-medium hover:bg-purple-600 transition-colors">
              <ExternalLink className="w-4 h-4" />
              API Docs
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

