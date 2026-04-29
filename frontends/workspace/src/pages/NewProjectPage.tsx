import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { 
  ArrowLeft,
  Plus,
  FolderGit2,
  Upload,
  Github,
  Code2,
  Sparkles
} from 'lucide-react'

export default function NewProjectPage() {
  const navigate = useNavigate()
  const [projectName, setProjectName] = useState('')
  const [projectType, setProjectType] = useState<'blank' | 'template' | 'import'>('blank')

  const templates = [
    { id: 'react', name: 'React App', desc: 'React 18 with TypeScript' },
    { id: 'next', name: 'Next.js', desc: 'Full-stack React framework' },
    { id: 'node', name: 'Node.js API', desc: 'Express REST API' },
    { id: 'python', name: 'Python FastAPI', desc: 'Modern Python API' },
  ]

  const handleCreate = () => {
    if (projectName.trim()) {
      navigate('/ide')
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate('/')}
          className="p-2 hover:bg-white/10 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Create New Project</h1>
          <p className="text-white/50">Start a new project from scratch or template</p>
        </div>
      </div>

      {/* Project Type */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Project Type</h2>
        <div className="grid grid-cols-3 gap-4">
          <button
            onClick={() => setProjectType('blank')}
            className={`p-4 rounded-xl border transition-all ${
              projectType === 'blank'
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-white/10 bg-white/5 hover:bg-white/10'
            }`}
          >
            <Code2 className="w-8 h-8 text-emerald-400 mb-2" />
            <h3 className="font-medium">Blank Project</h3>
            <p className="text-sm text-white/50">Start fresh</p>
          </button>
          <button
            onClick={() => setProjectType('template')}
            className={`p-4 rounded-xl border transition-all ${
              projectType === 'template'
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-white/10 bg-white/5 hover:bg-white/10'
            }`}
          >
            <Sparkles className="w-8 h-8 text-purple-400 mb-2" />
            <h3 className="font-medium">From Template</h3>
            <p className="text-sm text-white/50">Quick start</p>
          </button>
          <button
            onClick={() => navigate('/connect-repo')}
            className={`p-4 rounded-xl border transition-all ${
              projectType === 'import'
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-white/10 bg-white/5 hover:bg-white/10'
            }`}
          >
            <Github className="w-8 h-8 text-white mb-2" />
            <h3 className="font-medium">Import Repo</h3>
            <p className="text-sm text-white/50">From GitHub</p>
          </button>
        </div>
      </div>

      {/* Project Name */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Project Name</h2>
        <input
          type="text"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="my-awesome-project"
          className="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-xl focus:outline-none focus:border-emerald-500/50"
        />
      </div>

      {/* Templates */}
      {projectType === 'template' && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Choose Template</h2>
          <div className="grid grid-cols-2 gap-4">
            {templates.map((template) => (
              <button
                key={template.id}
                className="p-4 bg-black/30 rounded-lg hover:bg-black/50 transition-colors text-left"
              >
                <h3 className="font-medium">{template.name}</h3>
                <p className="text-sm text-white/50">{template.desc}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-3">
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 text-white/60 hover:text-white transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={!projectName.trim()}
          className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Project
        </button>
      </div>
    </div>
  )
}

