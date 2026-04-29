import { useNavigate } from 'react-router-dom'
import { 
  ArrowLeft,
  PlayCircle,
  Clock,
  BookOpen,
  Rocket,
  Code2,
  Brain,
  GitBranch,
  Zap
} from 'lucide-react'

export default function TutorialsPage() {
  const navigate = useNavigate()

  const tutorials = [
    {
      category: 'Getting Started',
      items: [
        { title: 'Introduction to code4u.ai', duration: '3 min', icon: Rocket, completed: true },
        { title: 'Connecting Your First Repository', duration: '5 min', icon: GitBranch, completed: false },
        { title: 'Understanding the IDE', duration: '7 min', icon: Code2, completed: false },
      ]
    },
    {
      category: 'AI Features',
      items: [
        { title: 'Working with AI Agents', duration: '10 min', icon: Brain, completed: false },
        { title: 'Quick Refactor Tool', duration: '4 min', icon: Zap, completed: false },
        { title: 'AI-Powered Code Completion', duration: '6 min', icon: Code2, completed: false },
      ]
    },
    {
      category: 'Advanced Topics',
      items: [
        { title: 'Team Collaboration', duration: '8 min', icon: BookOpen, completed: false },
        { title: 'Custom Agent Instructions', duration: '12 min', icon: Brain, completed: false },
        { title: 'CI/CD Integration', duration: '15 min', icon: Rocket, completed: false },
      ]
    }
  ]

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
          <h1 className="text-2xl font-bold">Tutorials & Demos</h1>
          <p className="text-white/50">Learn how to use code4u.ai effectively</p>
        </div>
      </div>

      {/* Featured Video */}
      <div className="bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 rounded-xl p-6">
        <div className="flex items-center gap-6">
          <div className="w-48 h-28 bg-black/40 rounded-lg flex items-center justify-center relative group cursor-pointer">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg" />
            <PlayCircle className="w-12 h-12 text-white group-hover:scale-110 transition-transform" />
          </div>
          <div>
            <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs font-medium">Featured</span>
            <h2 className="text-xl font-semibold mt-2 mb-1">Complete Platform Walkthrough</h2>
            <p className="text-white/60 mb-3">Learn everything about code4u.ai in this comprehensive guide</p>
            <div className="flex items-center gap-4 text-sm text-white/50">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                20 minutes
              </span>
              <span>Updated 2 days ago</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tutorial Categories */}
      {tutorials.map((category) => (
        <div key={category.category} className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">{category.category}</h2>
          <div className="space-y-2">
            {category.items.map((tutorial, i) => (
              <button
                key={i}
                className="w-full flex items-center justify-between p-4 bg-black/30 rounded-lg hover:bg-black/50 transition-colors text-left group"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    tutorial.completed ? 'bg-emerald-500/20' : 'bg-white/10'
                  }`}>
                    <tutorial.icon className={`w-5 h-5 ${
                      tutorial.completed ? 'text-emerald-400' : 'text-white/70'
                    }`} />
                  </div>
                  <div>
                    <h3 className="font-medium group-hover:text-emerald-400 transition-colors">
                      {tutorial.title}
                    </h3>
                    <p className="text-sm text-white/50">{tutorial.duration}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {tutorial.completed && (
                    <span className="text-sm text-emerald-400">Completed</span>
                  )}
                  <PlayCircle className="w-8 h-8 text-white/20 group-hover:text-emerald-400 transition-colors" />
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Help Section */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold mb-1">Need more help?</h3>
            <p className="text-sm text-white/50">Check our documentation or join our community</p>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={() => navigate('/docs')}
              className="px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-sm font-medium hover:bg-white/20 transition-colors"
            >
              Documentation
            </button>
            <a
              href="https://discord.gg/code4u"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg text-sm font-medium"
            >
              Join Discord
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

