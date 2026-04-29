/**
 * Models Management Page
 */
import React, { useState } from 'react';
import { 
  Cpu, Zap, Clock, DollarSign, BarChart2, Settings, 
  Play, Pause, RefreshCw, ChevronRight, AlertCircle
} from 'lucide-react';

interface Model {
  id: string;
  name: string;
  provider: 'self-hosted' | 'openai' | 'anthropic' | 'google';
  type: 'base' | 'fine-tuned' | 'lora';
  status: 'active' | 'loading' | 'stopped' | 'error';
  metrics: { latency: number; throughput: number; accuracy: number; cost: number };
  gpu: string;
  memory: string;
  requests: number;
}

const mockModels: Model[] = [
  { id: '1', name: 'DeepSeek Coder V2', provider: 'self-hosted', type: 'base', status: 'active', metrics: { latency: 124, throughput: 850, accuracy: 92, cost: 0.001 }, gpu: 'A100 80GB', memory: '72GB', requests: 45230 },
  { id: '2', name: 'CodeLlama 70B', provider: 'self-hosted', type: 'base', status: 'active', metrics: { latency: 156, throughput: 620, accuracy: 88, cost: 0.002 }, gpu: 'A100 80GB x2', memory: '145GB', requests: 32100 },
  { id: '3', name: 'Acme-LoRA-Refactor', provider: 'self-hosted', type: 'lora', status: 'active', metrics: { latency: 132, throughput: 780, accuracy: 94, cost: 0.001 }, gpu: 'L40S', memory: '48GB', requests: 12400 },
  { id: '4', name: 'GPT-4o (Fallback)', provider: 'openai', type: 'base', status: 'active', metrics: { latency: 245, throughput: 2400, accuracy: 96, cost: 0.015 }, gpu: 'Cloud', memory: '-', requests: 890 },
  { id: '5', name: 'Claude Sonnet 4', provider: 'anthropic', type: 'base', status: 'active', metrics: { latency: 198, throughput: 1800, accuracy: 95, cost: 0.012 }, gpu: 'Cloud', memory: '-', requests: 654 },
  { id: '6', name: 'Gemini Pro 2.0', provider: 'google', type: 'base', status: 'stopped', metrics: { latency: 0, throughput: 0, accuracy: 0, cost: 0.008 }, gpu: 'Cloud', memory: '-', requests: 0 },
  { id: '7', name: 'FinanceX-LoRA', provider: 'self-hosted', type: 'lora', status: 'loading', metrics: { latency: 0, throughput: 0, accuracy: 0, cost: 0.001 }, gpu: 'L40S', memory: '48GB', requests: 0 },
];

const providerColors = {
  'self-hosted': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  'openai': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  'anthropic': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  'google': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

const statusConfig = {
  active: { color: 'text-emerald-500', bg: 'bg-emerald-500', label: 'Active' },
  loading: { color: 'text-amber-500', bg: 'bg-amber-500', label: 'Loading' },
  stopped: { color: 'text-slate-400', bg: 'bg-slate-400', label: 'Stopped' },
  error: { color: 'text-red-500', bg: 'bg-red-500', label: 'Error' },
};

export function ModelsPage() {
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  const selfHosted = mockModels.filter(m => m.provider === 'self-hosted');
  const cloud = mockModels.filter(m => m.provider !== 'self-hosted');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Model Management</h2>
          <p className="text-slate-500 dark:text-slate-400">Configure and monitor LLM models</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
            <RefreshCw size={18} />
            Refresh
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 transition-colors">
            <Cpu size={18} />
            Deploy Model
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <Cpu className="text-emerald-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Active Models</p>
              <p className="text-xl font-bold">{mockModels.filter(m => m.status === 'active').length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/10 rounded-lg">
              <Zap className="text-cyan-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Avg Latency</p>
              <p className="text-xl font-bold">156ms</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <BarChart2 className="text-purple-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Requests Today</p>
              <p className="text-xl font-bold">{mockModels.reduce((s, m) => s + m.requests, 0).toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <DollarSign className="text-amber-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Cloud Spend Today</p>
              <p className="text-xl font-bold">$24.67</p>
            </div>
          </div>
        </div>
      </div>

      {/* Self-Hosted Models */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            Self-Hosted Models
          </h3>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {selfHosted.map(model => (
            <div key={model.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${statusConfig[model.status].bg} ${model.status === 'loading' ? 'animate-pulse' : ''}`} />
                  <div>
                    <p className="font-medium">{model.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`px-2 py-0.5 rounded text-xs ${providerColors[model.provider]}`}>
                        {model.type === 'lora' ? 'LoRA' : 'Base'}
                      </span>
                      <span className="text-xs text-slate-500">{model.gpu}</span>
                      <span className="text-xs text-slate-500">•</span>
                      <span className="text-xs text-slate-500">{model.memory}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  {model.status === 'active' && (
                    <>
                      <div className="text-center">
                        <p className="text-sm font-medium">{model.metrics.latency}ms</p>
                        <p className="text-xs text-slate-500">Latency</p>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium">{model.metrics.accuracy}%</p>
                        <p className="text-xs text-slate-500">Accuracy</p>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium">{model.requests.toLocaleString()}</p>
                        <p className="text-xs text-slate-500">Requests</p>
                      </div>
                    </>
                  )}
                  <div className="flex items-center gap-2">
                    {model.status === 'active' ? (
                      <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-amber-500">
                        <Pause size={18} />
                      </button>
                    ) : (
                      <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-emerald-500">
                        <Play size={18} />
                      </button>
                    )}
                    <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                      <Settings size={18} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Cloud Models */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            Cloud Models (Premium Fallback)
          </h3>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {cloud.map(model => (
            <div key={model.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${statusConfig[model.status].bg}`} />
                  <div>
                    <p className="font-medium">{model.name}</p>
                    <span className={`px-2 py-0.5 rounded text-xs ${providerColors[model.provider]}`}>
                      {model.provider}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  {model.status === 'active' && (
                    <>
                      <div className="text-center">
                        <p className="text-sm font-medium">${model.metrics.cost}/1K</p>
                        <p className="text-xs text-slate-500">Cost</p>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium">{model.requests.toLocaleString()}</p>
                        <p className="text-xs text-slate-500">Requests</p>
                      </div>
                    </>
                  )}
                  <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                    <Settings size={18} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

