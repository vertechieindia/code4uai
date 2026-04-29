/**
 * MCP Marketplace Page
 */
import React, { useState } from 'react';
import { 
  Store, Search, Download, Check, Star, ExternalLink,
  Globe, Database, FileCode, Terminal, Shield, Zap,
  Settings, Trash2, RefreshCw
} from 'lucide-react';

interface MCPServer {
  id: string;
  name: string;
  description: string;
  category: string;
  publisher: string;
  verified: boolean;
  rating: number;
  downloads: number;
  installed: boolean;
  version: string;
  icon: React.ReactNode;
}

const categories = [
  { id: 'all', label: 'All', count: 24 },
  { id: 'browser', label: 'Browser', count: 4 },
  { id: 'database', label: 'Database', count: 6 },
  { id: 'api', label: 'API', count: 5 },
  { id: 'file', label: 'File System', count: 3 },
  { id: 'devops', label: 'DevOps', count: 4 },
  { id: 'security', label: 'Security', count: 2 },
];

const mockServers: MCPServer[] = [
  { id: '1', name: 'Puppeteer Browser', description: 'Control Chrome browser for testing and automation', category: 'browser', publisher: 'MCP Labs', verified: true, rating: 4.8, downloads: 45200, installed: true, version: '2.1.0', icon: <Globe size={24} /> },
  { id: '2', name: 'PostgreSQL', description: 'Query and manage PostgreSQL databases', category: 'database', publisher: 'MCP Labs', verified: true, rating: 4.9, downloads: 89000, installed: true, version: '1.5.2', icon: <Database size={24} /> },
  { id: '3', name: 'GitHub API', description: 'Interact with GitHub repositories and issues', category: 'api', publisher: 'GitHub', verified: true, rating: 4.7, downloads: 123000, installed: false, version: '3.0.1', icon: <FileCode size={24} /> },
  { id: '4', name: 'Shell Executor', description: 'Run shell commands securely in sandboxed environment', category: 'devops', publisher: 'MCP Labs', verified: true, rating: 4.5, downloads: 34500, installed: true, version: '1.2.0', icon: <Terminal size={24} /> },
  { id: '5', name: 'AWS SDK', description: 'Manage AWS resources and services', category: 'api', publisher: 'AWS', verified: true, rating: 4.6, downloads: 67800, installed: false, version: '2.0.0', icon: <Zap size={24} /> },
  { id: '6', name: 'MongoDB', description: 'Query and manage MongoDB databases', category: 'database', publisher: 'MongoDB Inc', verified: true, rating: 4.7, downloads: 56000, installed: false, version: '1.3.1', icon: <Database size={24} /> },
  { id: '7', name: 'Vault Secrets', description: 'Securely access HashiCorp Vault secrets', category: 'security', publisher: 'HashiCorp', verified: true, rating: 4.9, downloads: 23400, installed: false, version: '1.1.0', icon: <Shield size={24} /> },
  { id: '8', name: 'Playwright', description: 'Cross-browser testing and automation', category: 'browser', publisher: 'Microsoft', verified: true, rating: 4.8, downloads: 78900, installed: false, version: '1.4.0', icon: <Globe size={24} /> },
];

export function MCPPage() {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [showInstalled, setShowInstalled] = useState(false);

  const filteredServers = mockServers.filter(s => {
    const matchesSearch = s.name.toLowerCase().includes(search.toLowerCase()) ||
                         s.description.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = activeCategory === 'all' || s.category === activeCategory;
    const matchesInstalled = !showInstalled || s.installed;
    return matchesSearch && matchesCategory && matchesInstalled;
  });

  const installedCount = mockServers.filter(s => s.installed).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">MCP Marketplace</h2>
          <p className="text-slate-500 dark:text-slate-400">Browse and install Model Context Protocol servers</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{installedCount} installed</span>
          <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800">
            <RefreshCw size={18} />
            Check Updates
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search MCP servers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
        </div>
        <button
          onClick={() => setShowInstalled(!showInstalled)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            showInstalled 
              ? 'bg-cyan-500 text-white' 
              : 'border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'
          }`}
        >
          <Check size={18} />
          Installed Only
        </button>
      </div>

      {/* Categories */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {categories.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
              activeCategory === cat.id
                ? 'bg-cyan-500 text-white'
                : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-cyan-500'
            }`}
          >
            {cat.label}
            <span className="ml-2 opacity-70">{cat.count}</span>
          </button>
        ))}
      </div>

      {/* Server Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredServers.map(server => (
          <div key={server.id} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm border border-slate-200 dark:border-slate-700 hover:border-cyan-500 transition-colors">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-100 dark:bg-slate-700 rounded-lg text-slate-600 dark:text-slate-300">
                  {server.icon}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-semibold">{server.name}</h4>
                    {server.verified && (
                      <span className="text-cyan-500" title="Verified">
                        <Check size={14} />
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">{server.publisher}</p>
                </div>
              </div>
              {server.installed && (
                <span className="px-2 py-1 bg-emerald-500/10 text-emerald-500 text-xs rounded-full">
                  Installed
                </span>
              )}
            </div>

            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 line-clamp-2">
              {server.description}
            </p>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-slate-500">
                <span className="flex items-center gap-1">
                  <Star size={14} className="text-amber-500" />
                  {server.rating}
                </span>
                <span>{(server.downloads / 1000).toFixed(0)}k</span>
                <span className="text-xs">v{server.version}</span>
              </div>
              
              {server.installed ? (
                <div className="flex items-center gap-2">
                  <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                    <Settings size={16} />
                  </button>
                  <button className="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-500">
                    <Trash2 size={16} />
                  </button>
                </div>
              ) : (
                <button className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500 text-white text-sm rounded-lg hover:bg-cyan-600">
                  <Download size={14} />
                  Install
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

