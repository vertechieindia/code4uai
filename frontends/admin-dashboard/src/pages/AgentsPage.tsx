/**
 * Agent Runs Page
 */
import React, { useState } from 'react';
import { 
  GitBranch, Clock, CheckCircle, XCircle, Loader, Filter,
  ChevronDown, Eye, RotateCcw, AlertTriangle, Play, Pause
} from 'lucide-react';

interface AgentRun {
  id: string;
  tenant: string;
  task: string;
  type: 'refactor' | 'add_api' | 'fix_bug' | 'explain' | 'generate';
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'review';
  state: string;
  startTime: string;
  duration: string;
  files: number;
  tokens: number;
  model: string;
}

const mockRuns: AgentRun[] = [
  { id: 'run-001', tenant: 'Acme Corp', task: 'Rename email to primaryEmail across all services', type: 'refactor', status: 'completed', state: 'APPLIED', startTime: '2 min ago', duration: '12s', files: 8, tokens: 4520, model: 'DeepSeek Coder' },
  { id: 'run-002', tenant: 'TechStart', task: 'Add authentication middleware to API routes', type: 'add_api', status: 'running', state: 'CODE_GENERATED', startTime: '5 min ago', duration: '45s', files: 3, tokens: 2890, model: 'CodeLlama 70B' },
  { id: 'run-003', tenant: 'FinanceX', task: 'Refactor payment module for new processor', type: 'refactor', status: 'review', state: 'READY_FOR_REVIEW', startTime: '12 min ago', duration: '1m 23s', files: 12, tokens: 8900, model: 'GPT-4o' },
  { id: 'run-004', tenant: 'HealthTech', task: 'Fix API validation bug in patient endpoint', type: 'fix_bug', status: 'failed', state: 'FAILED', startTime: '15 min ago', duration: '8s', files: 0, tokens: 1200, model: 'DeepSeek Coder' },
  { id: 'run-005', tenant: 'Acme Corp', task: 'Add dark mode toggle to settings', type: 'generate', status: 'completed', state: 'APPLIED', startTime: '20 min ago', duration: '34s', files: 4, tokens: 3200, model: 'DeepSeek Coder' },
  { id: 'run-006', tenant: 'DataDriven', task: 'Generate CRUD endpoints for analytics model', type: 'add_api', status: 'completed', state: 'APPLIED', startTime: '25 min ago', duration: '56s', files: 6, tokens: 5600, model: 'CodeLlama 70B' },
  { id: 'run-007', tenant: 'CloudNative', task: 'Explain authentication flow', type: 'explain', status: 'completed', state: 'APPLIED', startTime: '30 min ago', duration: '4s', files: 0, tokens: 890, model: 'DeepSeek Coder' },
  { id: 'run-008', tenant: 'RetailCo', task: 'Fix inventory sync issue', type: 'fix_bug', status: 'queued', state: 'INIT', startTime: '32 min ago', duration: '-', files: 0, tokens: 0, model: '-' },
];

const statusConfig = {
  queued: { color: 'text-slate-500 bg-slate-500/10', icon: Clock, label: 'Queued' },
  running: { color: 'text-cyan-500 bg-cyan-500/10', icon: Loader, label: 'Running' },
  completed: { color: 'text-emerald-500 bg-emerald-500/10', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'text-red-500 bg-red-500/10', icon: XCircle, label: 'Failed' },
  cancelled: { color: 'text-slate-400 bg-slate-400/10', icon: XCircle, label: 'Cancelled' },
  review: { color: 'text-amber-500 bg-amber-500/10', icon: Eye, label: 'Review' },
};

const typeColors = {
  refactor: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  add_api: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  fix_bug: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  explain: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  generate: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
};

export function AgentsPage() {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [isLive, setIsLive] = useState(true);

  const filteredRuns = mockRuns.filter(r => filterStatus === 'all' || r.status === filterStatus);

  const stats = {
    total: mockRuns.length,
    running: mockRuns.filter(r => r.status === 'running').length,
    completed: mockRuns.filter(r => r.status === 'completed').length,
    failed: mockRuns.filter(r => r.status === 'failed').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Agent Runs</h2>
          <p className="text-slate-500 dark:text-slate-400">Monitor and manage agent executions</p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors ${
              isLive 
                ? 'border-emerald-500 bg-emerald-500/10 text-emerald-600' 
                : 'border-slate-200 dark:border-slate-700'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
            {isLive ? 'Live' : 'Paused'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Total Today</p>
              <p className="text-2xl font-bold mt-1">{stats.total}</p>
            </div>
            <GitBranch className="text-slate-400" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Running</p>
              <p className="text-2xl font-bold mt-1 text-cyan-500">{stats.running}</p>
            </div>
            <Loader className="text-cyan-500 animate-spin" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Completed</p>
              <p className="text-2xl font-bold mt-1 text-emerald-500">{stats.completed}</p>
            </div>
            <CheckCircle className="text-emerald-500" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Failed</p>
              <p className="text-2xl font-bold mt-1 text-red-500">{stats.failed}</p>
            </div>
            <XCircle className="text-red-500" size={24} />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <select 
          value={filterStatus} 
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
        >
          <option value="all">All Status</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="review">Awaiting Review</option>
        </select>
      </div>

      {/* Runs List */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {filteredRuns.map(run => {
            const StatusIcon = statusConfig[run.status].icon;
            return (
              <div key={run.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${statusConfig[run.status].color}`}>
                      <StatusIcon size={20} className={run.status === 'running' ? 'animate-spin' : ''} />
                    </div>
                    <div>
                      <p className="font-medium">{run.task}</p>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-sm text-slate-500">{run.tenant}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${typeColors[run.type]}`}>
                          {run.type}
                        </span>
                        <span className="text-xs text-slate-400">State: {run.state}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <p className="text-sm font-medium">{run.duration}</p>
                      <p className="text-xs text-slate-500">{run.startTime}</p>
                    </div>
                    {run.status !== 'queued' && (
                      <div className="text-right">
                        <p className="text-sm">{run.files} files</p>
                        <p className="text-xs text-slate-500">{run.tokens.toLocaleString()} tokens</p>
                      </div>
                    )}
                    <div className="text-right min-w-[100px]">
                      <p className="text-sm text-slate-600 dark:text-slate-400">{run.model}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                        <Eye size={18} />
                      </button>
                      {run.status === 'failed' && (
                        <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-amber-500">
                          <RotateCcw size={18} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

