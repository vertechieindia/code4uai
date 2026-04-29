/**
 * Knowledge Items & Memories Page
 */
import React, { useState } from 'react';
import { 
  Brain, Search, Plus, Edit, Trash2, Tag, Clock,
  FileText, Code, AlertCircle, CheckCircle, Star
} from 'lucide-react';

interface KnowledgeItem {
  id: string;
  type: 'rule' | 'pattern' | 'context' | 'fact' | 'preference';
  title: string;
  content: string;
  scope: 'global' | 'project' | 'file';
  tenant: string;
  tags: string[];
  createdAt: string;
  usageCount: number;
  active: boolean;
}

interface Memory {
  id: string;
  agentId: string;
  tenant: string;
  summary: string;
  context: string;
  timestamp: string;
  importance: 'high' | 'medium' | 'low';
}

const mockKnowledge: KnowledgeItem[] = [
  { id: '1', type: 'rule', title: 'No direct database queries in controllers', content: 'All database operations must go through the repository layer. Controllers should only interact with services.', scope: 'global', tenant: 'All', tags: ['architecture', 'best-practice'], createdAt: '2 days ago', usageCount: 234, active: true },
  { id: '2', type: 'pattern', title: 'Error handling pattern', content: 'Use Result<T, E> pattern for error handling. Never throw exceptions in business logic.', scope: 'global', tenant: 'All', tags: ['error-handling', 'pattern'], createdAt: '5 days ago', usageCount: 189, active: true },
  { id: '3', type: 'context', title: 'Payment service architecture', content: 'Payment service uses Stripe as primary processor with PayPal as fallback. All transactions are logged in audit table.', scope: 'project', tenant: 'FinanceX', tags: ['payments', 'architecture'], createdAt: '1 week ago', usageCount: 56, active: true },
  { id: '4', type: 'preference', title: 'Prefer functional style', content: 'Use map, filter, reduce over for loops. Prefer immutable data structures.', scope: 'global', tenant: 'All', tags: ['style', 'functional'], createdAt: '2 weeks ago', usageCount: 345, active: true },
  { id: '5', type: 'fact', title: 'API rate limits', content: 'External API rate limit is 1000 requests per minute. Implement exponential backoff for retries.', scope: 'project', tenant: 'TechStart', tags: ['api', 'limits'], createdAt: '3 weeks ago', usageCount: 78, active: true },
];

const mockMemories: Memory[] = [
  { id: '1', agentId: 'agent-001', tenant: 'Acme Corp', summary: 'User prefers TypeScript strict mode', context: 'During refactor task, user corrected agent to use strict mode', timestamp: '1 hour ago', importance: 'high' },
  { id: '2', agentId: 'agent-002', tenant: 'TechStart', summary: 'Project uses Prisma for ORM', context: 'Learned during database query generation', timestamp: '3 hours ago', importance: 'medium' },
  { id: '3', agentId: 'agent-001', tenant: 'FinanceX', summary: 'Authentication uses OAuth2 with Okta', context: 'User mentioned during auth flow discussion', timestamp: '5 hours ago', importance: 'high' },
  { id: '4', agentId: 'agent-003', tenant: 'Acme Corp', summary: 'Frontend uses Tailwind CSS', context: 'Observed from existing code patterns', timestamp: '1 day ago', importance: 'low' },
];

const typeConfig = {
  rule: { color: 'bg-red-500/10 text-red-500', icon: AlertCircle },
  pattern: { color: 'bg-purple-500/10 text-purple-500', icon: Code },
  context: { color: 'bg-blue-500/10 text-blue-500', icon: FileText },
  fact: { color: 'bg-green-500/10 text-green-500', icon: CheckCircle },
  preference: { color: 'bg-amber-500/10 text-amber-500', icon: Star },
};

const importanceColors = {
  high: 'bg-red-500/10 text-red-500',
  medium: 'bg-amber-500/10 text-amber-500',
  low: 'bg-slate-500/10 text-slate-500',
};

export function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<'items' | 'memories'>('items');
  const [search, setSearch] = useState('');

  const filteredKnowledge = mockKnowledge.filter(k => 
    k.title.toLowerCase().includes(search.toLowerCase()) ||
    k.content.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Knowledge & Memories</h2>
          <p className="text-slate-500 dark:text-slate-400">Manage rules, patterns, and agent memories</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600">
          <Plus size={18} />
          Add Knowledge
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Total Items</p>
          <p className="text-2xl font-bold mt-1">{mockKnowledge.length}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Agent Memories</p>
          <p className="text-2xl font-bold mt-1">{mockMemories.length}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Total Usage</p>
          <p className="text-2xl font-bold mt-1">{mockKnowledge.reduce((s, k) => s + k.usageCount, 0).toLocaleString()}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Active Rules</p>
          <p className="text-2xl font-bold mt-1 text-emerald-500">{mockKnowledge.filter(k => k.active).length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200 dark:border-slate-700">
        <button 
          onClick={() => setActiveTab('items')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'items' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Knowledge Items
        </button>
        <button 
          onClick={() => setActiveTab('memories')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'memories' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Agent Memories
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Search knowledge..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
        />
      </div>

      {/* Knowledge Items Tab */}
      {activeTab === 'items' && (
        <div className="space-y-4">
          {filteredKnowledge.map(item => {
            const TypeIcon = typeConfig[item.type].icon;
            return (
              <div key={item.id} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${typeConfig[item.type].color}`}>
                      <TypeIcon size={20} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h4 className="font-semibold">{item.title}</h4>
                        <span className={`px-2 py-0.5 rounded text-xs capitalize ${typeConfig[item.type].color}`}>
                          {item.type}
                        </span>
                        <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400">
                          {item.scope}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                        {item.content}
                      </p>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          {item.tags.map(tag => (
                            <span key={tag} className="flex items-center gap-1 px-2 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-xs">
                              <Tag size={10} />
                              {tag}
                            </span>
                          ))}
                        </div>
                        <span className="text-xs text-slate-500">Used {item.usageCount} times</span>
                        <span className="text-xs text-slate-500">{item.createdAt}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                      <Edit size={16} />
                    </button>
                    <button className="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-500">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Memories Tab */}
      {activeTab === 'memories' && (
        <div className="space-y-4">
          {mockMemories.map(memory => (
            <div key={memory.id} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="p-2 bg-purple-500/10 rounded-lg">
                    <Brain className="text-purple-500" size={20} />
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="font-semibold">{memory.summary}</h4>
                      <span className={`px-2 py-0.5 rounded text-xs capitalize ${importanceColors[memory.importance]}`}>
                        {memory.importance}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                      {memory.context}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span>{memory.tenant}</span>
                      <span>•</span>
                      <span>{memory.agentId}</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock size={12} />
                        {memory.timestamp}
                      </span>
                    </div>
                  </div>
                </div>
                <button className="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-500">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

