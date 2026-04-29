/**
 * Tenants Management Page
 */
import React, { useState } from 'react';
import { 
  Plus, Search, Filter, MoreVertical, ExternalLink, 
  AlertTriangle, CheckCircle, XCircle, Settings
} from 'lucide-react';

interface Tenant {
  id: string;
  name: string;
  email: string;
  tier: 'Developer' | 'Team' | 'Enterprise';
  status: 'active' | 'warning' | 'suspended' | 'trial';
  usage: { agents: number; tokens: number; storage: number };
  createdAt: string;
  lastActive: string;
  members: number;
}

const mockTenants: Tenant[] = [
  { id: '1', name: 'Acme Corporation', email: 'admin@acme.com', tier: 'Enterprise', status: 'active', usage: { agents: 156, tokens: 2400000, storage: 45 }, createdAt: '2024-06-15', lastActive: '2 min ago', members: 85 },
  { id: '2', name: 'TechStart Inc', email: 'tech@techstart.io', tier: 'Team', status: 'active', usage: { agents: 42, tokens: 580000, storage: 12 }, createdAt: '2024-08-22', lastActive: '5 min ago', members: 12 },
  { id: '3', name: 'FinanceX', email: 'ops@financex.com', tier: 'Enterprise', status: 'warning', usage: { agents: 234, tokens: 4800000, storage: 89 }, createdAt: '2024-03-10', lastActive: '1 hour ago', members: 156 },
  { id: '4', name: 'HealthTech Solutions', email: 'it@healthtech.com', tier: 'Team', status: 'active', usage: { agents: 28, tokens: 320000, storage: 8 }, createdAt: '2024-09-01', lastActive: '15 min ago', members: 8 },
  { id: '5', name: 'RetailCo', email: 'dev@retailco.com', tier: 'Developer', status: 'trial', usage: { agents: 5, tokens: 45000, storage: 2 }, createdAt: '2024-12-20', lastActive: '3 hours ago', members: 2 },
  { id: '6', name: 'DataDriven Labs', email: 'admin@datadriven.ai', tier: 'Enterprise', status: 'active', usage: { agents: 89, tokens: 1200000, storage: 34 }, createdAt: '2024-05-18', lastActive: '30 min ago', members: 45 },
  { id: '7', name: 'CloudNative Corp', email: 'cloud@native.io', tier: 'Team', status: 'suspended', usage: { agents: 0, tokens: 0, storage: 15 }, createdAt: '2024-04-12', lastActive: '7 days ago', members: 18 },
];

const statusConfig = {
  active: { color: 'text-emerald-500 bg-emerald-500/10', icon: CheckCircle, label: 'Active' },
  warning: { color: 'text-amber-500 bg-amber-500/10', icon: AlertTriangle, label: 'Warning' },
  suspended: { color: 'text-red-500 bg-red-500/10', icon: XCircle, label: 'Suspended' },
  trial: { color: 'text-blue-500 bg-blue-500/10', icon: CheckCircle, label: 'Trial' },
};

const tierColors = {
  Developer: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
  Team: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  Enterprise: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
};

export function TenantsPage() {
  const [search, setSearch] = useState('');
  const [filterTier, setFilterTier] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const filteredTenants = mockTenants.filter(t => {
    const matchesSearch = t.name.toLowerCase().includes(search.toLowerCase()) || 
                         t.email.toLowerCase().includes(search.toLowerCase());
    const matchesTier = filterTier === 'all' || t.tier === filterTier;
    const matchesStatus = filterStatus === 'all' || t.status === filterStatus;
    return matchesSearch && matchesTier && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Tenant Management</h2>
          <p className="text-slate-500 dark:text-slate-400">Manage all customer tenants and their resources</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 transition-colors">
          <Plus size={20} />
          Add Tenant
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Total Tenants</p>
          <p className="text-2xl font-bold mt-1">{mockTenants.length}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Active</p>
          <p className="text-2xl font-bold mt-1 text-emerald-500">{mockTenants.filter(t => t.status === 'active').length}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Enterprise</p>
          <p className="text-2xl font-bold mt-1 text-purple-500">{mockTenants.filter(t => t.tier === 'Enterprise').length}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <p className="text-sm text-slate-500">Total Members</p>
          <p className="text-2xl font-bold mt-1">{mockTenants.reduce((sum, t) => sum + t.members, 0)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search tenants..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
        </div>
        <select 
          value={filterTier} 
          onChange={(e) => setFilterTier(e.target.value)}
          className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
        >
          <option value="all">All Tiers</option>
          <option value="Developer">Developer</option>
          <option value="Team">Team</option>
          <option value="Enterprise">Enterprise</option>
        </select>
        <select 
          value={filterStatus} 
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="warning">Warning</option>
          <option value="suspended">Suspended</option>
          <option value="trial">Trial</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-900/50">
            <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              <th className="py-3 px-4 font-medium">Tenant</th>
              <th className="py-3 px-4 font-medium">Tier</th>
              <th className="py-3 px-4 font-medium">Status</th>
              <th className="py-3 px-4 font-medium">Usage</th>
              <th className="py-3 px-4 font-medium">Members</th>
              <th className="py-3 px-4 font-medium">Last Active</th>
              <th className="py-3 px-4 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {filteredTenants.map((tenant) => {
              const StatusIcon = statusConfig[tenant.status].icon;
              return (
                <tr key={tenant.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center text-white font-bold">
                        {tenant.name.charAt(0)}
                      </div>
                      <div>
                        <p className="font-medium">{tenant.name}</p>
                        <p className="text-sm text-slate-500">{tenant.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${tierColors[tenant.tier]}`}>
                      {tenant.tier}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className={`flex items-center gap-1.5 text-sm ${statusConfig[tenant.status].color} px-2 py-1 rounded-full w-fit`}>
                      <StatusIcon size={14} />
                      {statusConfig[tenant.status].label}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <div className="text-sm">
                      <p>{tenant.usage.agents.toLocaleString()} agents</p>
                      <p className="text-slate-500">{(tenant.usage.tokens / 1000000).toFixed(1)}M tokens</p>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm">{tenant.members}</span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-slate-500">{tenant.lastActive}</span>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <button className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400 hover:text-slate-600">
                        <ExternalLink size={16} />
                      </button>
                      <button className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400 hover:text-slate-600">
                        <Settings size={16} />
                      </button>
                      <button className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400 hover:text-slate-600">
                        <MoreVertical size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

