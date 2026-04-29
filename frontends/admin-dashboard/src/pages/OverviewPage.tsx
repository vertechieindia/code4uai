/**
 * Overview Dashboard Page
 */
import React from 'react';
import { 
  Activity, Users, Cpu, GitBranch, TrendingUp, 
  ArrowUpRight, ArrowDownRight
} from 'lucide-react';

interface Metric {
  label: string;
  value: string;
  change: string;
  trend: 'up' | 'down' | 'neutral';
}

interface Tenant {
  id: string;
  name: string;
  tier: string;
  usage: number;
  status: 'active' | 'warning' | 'inactive';
}

interface AgentRun {
  id: string;
  tenant: string;
  task: string;
  status: 'running' | 'completed' | 'failed';
  duration: string;
  time: string;
}

const metrics: Metric[] = [
  { label: 'Active Tenants', value: '47', change: '+5', trend: 'up' },
  { label: 'Agent Runs Today', value: '1,234', change: '+12%', trend: 'up' },
  { label: 'Avg Latency', value: '847ms', change: '-15%', trend: 'up' },
  { label: 'Success Rate', value: '98.7%', change: '+0.3%', trend: 'up' },
  { label: 'GPU Utilization', value: '67%', change: '+8%', trend: 'neutral' },
  { label: 'Premium Fallbacks', value: '3.2%', change: '-1.1%', trend: 'up' },
];

const tenants: Tenant[] = [
  { id: '1', name: 'Acme Corp', tier: 'Enterprise', usage: 85, status: 'active' },
  { id: '2', name: 'TechStart', tier: 'Team', usage: 42, status: 'active' },
  { id: '3', name: 'FinanceX', tier: 'Enterprise', usage: 91, status: 'warning' },
  { id: '4', name: 'HealthTech', tier: 'Team', usage: 23, status: 'active' },
  { id: '5', name: 'RetailCo', tier: 'Developer', usage: 67, status: 'active' },
];

const recentRuns: AgentRun[] = [
  { id: '1', tenant: 'Acme Corp', task: 'Rename email to primaryEmail', status: 'completed', duration: '12s', time: '2 min ago' },
  { id: '2', tenant: 'TechStart', task: 'Add authentication middleware', status: 'running', duration: '45s', time: '5 min ago' },
  { id: '3', tenant: 'FinanceX', task: 'Refactor payment module', status: 'completed', duration: '1m 23s', time: '12 min ago' },
  { id: '4', tenant: 'HealthTech', task: 'Fix API validation bug', status: 'failed', duration: '8s', time: '15 min ago' },
  { id: '5', tenant: 'Acme Corp', task: 'Add dark mode toggle', status: 'completed', duration: '34s', time: '20 min ago' },
];

function MetricCard({ metric }: { metric: Metric }) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm">
      <p className="text-sm text-slate-500 dark:text-slate-400">{metric.label}</p>
      <div className="flex items-end justify-between mt-2">
        <p className="text-2xl font-bold">{metric.value}</p>
        <span className={`flex items-center text-sm ${
          metric.trend === 'up' ? 'text-emerald-500' : 
          metric.trend === 'down' ? 'text-red-500' : 'text-slate-500'
        }`}>
          {metric.trend === 'up' ? <ArrowUpRight size={16} /> : metric.trend === 'down' ? <ArrowDownRight size={16} /> : null}
          {metric.change}
        </span>
      </div>
    </div>
  );
}

function TenantRow({ tenant }: { tenant: Tenant }) {
  return (
    <tr className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center text-white text-sm font-medium">
            {tenant.name.charAt(0)}
          </div>
          <span className="font-medium">{tenant.name}</span>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className={`px-2 py-1 rounded-full text-xs ${
          tenant.tier === 'Enterprise' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
          tenant.tier === 'Team' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
          'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
        }`}>
          {tenant.tier}
        </span>
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full ${
                tenant.usage > 80 ? 'bg-red-500' : 
                tenant.usage > 60 ? 'bg-yellow-500' : 'bg-emerald-500'
              }`}
              style={{ width: `${tenant.usage}%` }}
            />
          </div>
          <span className="text-sm text-slate-500">{tenant.usage}%</span>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className={`flex items-center gap-1 text-sm ${
          tenant.status === 'active' ? 'text-emerald-500' :
          tenant.status === 'warning' ? 'text-yellow-500' : 'text-slate-400'
        }`}>
          <span className="w-2 h-2 rounded-full bg-current" />
          {tenant.status}
        </span>
      </td>
      <td className="py-3 px-4">
        <button className="text-sm text-cyan-500 hover:text-cyan-600">View</button>
      </td>
    </tr>
  );
}

function AgentRunRow({ run }: { run: AgentRun }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700 last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${
          run.status === 'completed' ? 'bg-emerald-500' :
          run.status === 'running' ? 'bg-cyan-500 animate-pulse' : 'bg-red-500'
        }`} />
        <div>
          <p className="text-sm font-medium">{run.task}</p>
          <p className="text-xs text-slate-500">{run.tenant}</p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm">{run.duration}</p>
        <p className="text-xs text-slate-500">{run.time}</p>
      </div>
    </div>
  );
}

export function OverviewPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Dashboard Overview</h2>
        <p className="text-slate-500 dark:text-slate-400">Monitor your code4u.ai platform</p>
      </div>
      
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {metrics.map((metric, i) => (
          <MetricCard key={i} metric={metric} />
        ))}
      </div>
      
      {/* Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tenants Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm">
          <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
            <h3 className="font-semibold">Active Tenants</h3>
            <button className="text-sm text-cyan-500 hover:text-cyan-600">View All</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                  <th className="py-3 px-4 font-medium">Tenant</th>
                  <th className="py-3 px-4 font-medium">Tier</th>
                  <th className="py-3 px-4 font-medium">Usage</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((tenant) => (
                  <TenantRow key={tenant.id} tenant={tenant} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {/* Recent Agent Runs */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm">
          <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
            <h3 className="font-semibold">Recent Agent Runs</h3>
            <button className="text-sm text-cyan-500 hover:text-cyan-600">View All</button>
          </div>
          <div className="p-4">
            {recentRuns.map((run) => (
              <AgentRunRow key={run.id} run={run} />
            ))}
          </div>
        </div>
      </div>
      
      {/* Model Performance */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
        <h3 className="font-semibold mb-4">Model Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-4">
            <h4 className="text-sm text-slate-500">Self-Hosted Models</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>DeepSeek Coder V2</span>
                <span className="text-emerald-500">85% quality</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>CodeLlama 70B</span>
                <span className="text-emerald-500">78% quality</span>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <h4 className="text-sm text-slate-500">Premium Fallback Usage</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>GPT-4o</span>
                <span>42 requests today</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Claude Sonnet 4</span>
                <span>23 requests today</span>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <h4 className="text-sm text-slate-500">Cost Summary</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Today</span>
                <span className="font-medium">$12.47</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>This Month</span>
                <span className="font-medium">$342.89</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

