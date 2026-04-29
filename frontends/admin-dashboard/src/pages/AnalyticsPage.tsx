/**
 * Analytics Dashboard Page
 */
import React, { useState } from 'react';
import { 
  BarChart3, TrendingUp, Clock, Target, Zap, Users,
  ArrowUpRight, ArrowDownRight, Calendar
} from 'lucide-react';

interface Metric {
  label: string;
  value: string;
  change: number;
  trend: 'up' | 'down';
}

const metrics: Metric[] = [
  { label: 'Total Agent Runs', value: '45,230', change: 12, trend: 'up' },
  { label: 'Success Rate', value: '98.7%', change: 0.3, trend: 'up' },
  { label: 'Avg Latency', value: '847ms', change: -15, trend: 'up' },
  { label: 'Token Usage', value: '234M', change: 8, trend: 'up' },
];

const hourlyData = [
  { hour: '00:00', runs: 45, success: 44 },
  { hour: '02:00', runs: 23, success: 23 },
  { hour: '04:00', runs: 12, success: 12 },
  { hour: '06:00', runs: 34, success: 33 },
  { hour: '08:00', runs: 89, success: 87 },
  { hour: '10:00', runs: 156, success: 154 },
  { hour: '12:00', runs: 178, success: 176 },
  { hour: '14:00', runs: 234, success: 231 },
  { hour: '16:00', runs: 198, success: 195 },
  { hour: '18:00', runs: 145, success: 143 },
  { hour: '20:00', runs: 89, success: 88 },
  { hour: '22:00', runs: 56, success: 55 },
];

const topTenants = [
  { name: 'Acme Corp', runs: 12340, percentage: 27 },
  { name: 'FinanceX', runs: 9870, percentage: 22 },
  { name: 'DataDriven', runs: 6540, percentage: 14 },
  { name: 'TechStart', runs: 4560, percentage: 10 },
  { name: 'HealthTech', runs: 3210, percentage: 7 },
];

const taskTypes = [
  { type: 'Refactor', count: 15230, color: 'bg-purple-500' },
  { type: 'Add API', count: 12450, color: 'bg-blue-500' },
  { type: 'Fix Bug', count: 8920, color: 'bg-red-500' },
  { type: 'Generate', count: 5430, color: 'bg-cyan-500' },
  { type: 'Explain', count: 3200, color: 'bg-green-500' },
];

export function AnalyticsPage() {
  const [period, setPeriod] = useState('7d');
  const maxRuns = Math.max(...hourlyData.map(d => d.runs));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Analytics</h2>
          <p className="text-slate-500 dark:text-slate-400">Platform usage and performance metrics</p>
        </div>
        <div className="flex items-center gap-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-1">
          {['24h', '7d', '30d', '90d'].map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                period === p 
                  ? 'bg-cyan-500 text-white' 
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Top Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {metrics.map((metric, i) => (
          <div key={i} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
            <p className="text-sm text-slate-500">{metric.label}</p>
            <div className="flex items-end justify-between mt-2">
              <p className="text-2xl font-bold">{metric.value}</p>
              <span className={`flex items-center text-sm ${metric.trend === 'up' ? 'text-emerald-500' : 'text-red-500'}`}>
                {metric.trend === 'up' ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                {metric.change > 0 ? '+' : ''}{metric.change}%
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Hourly Activity Chart */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold mb-4">Agent Runs (24h)</h3>
          <div className="h-48 flex items-end gap-1">
            {hourlyData.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div 
                  className="w-full bg-cyan-500 rounded-t"
                  style={{ height: `${(d.runs / maxRuns) * 100}%` }}
                />
                <span className="text-xs text-slate-400">{d.hour.split(':')[0]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Task Types Distribution */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold mb-4">Task Distribution</h3>
          <div className="space-y-4">
            {taskTypes.map((task, i) => {
              const total = taskTypes.reduce((s, t) => s + t.count, 0);
              const percentage = (task.count / total) * 100;
              return (
                <div key={i}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{task.type}</span>
                    <span className="text-slate-500">{task.count.toLocaleString()} ({percentage.toFixed(0)}%)</span>
                  </div>
                  <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${task.color} rounded-full`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top Tenants & Model Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Tenants */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold mb-4">Top Tenants by Usage</h3>
          <div className="space-y-3">
            {topTenants.map((tenant, i) => (
              <div key={i} className="flex items-center gap-4">
                <span className="w-6 text-sm text-slate-400 font-medium">#{i + 1}</span>
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium">{tenant.name}</span>
                    <span className="text-slate-500">{tenant.runs.toLocaleString()} runs</span>
                  </div>
                  <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-full"
                      style={{ width: `${tenant.percentage}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Model Performance */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold mb-4">Model Performance</h3>
          <div className="space-y-4">
            {[
              { model: 'DeepSeek Coder V2', latency: 124, accuracy: 92, requests: 28500 },
              { model: 'CodeLlama 70B', latency: 156, accuracy: 88, requests: 12300 },
              { model: 'GPT-4o (Fallback)', latency: 245, accuracy: 96, requests: 890 },
              { model: 'Claude Sonnet 4', latency: 198, accuracy: 95, requests: 654 },
            ].map((model, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-700 last:border-0">
                <div>
                  <p className="font-medium">{model.model}</p>
                  <p className="text-xs text-slate-500">{model.requests.toLocaleString()} requests</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <p className="text-sm font-medium">{model.latency}ms</p>
                    <p className="text-xs text-slate-500">Latency</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-emerald-500">{model.accuracy}%</p>
                    <p className="text-xs text-slate-500">Accuracy</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

