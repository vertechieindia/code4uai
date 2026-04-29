/**
 * Infrastructure Monitoring Page
 */
import React from 'react';
import { 
  Server, Cpu, HardDrive, Activity, Wifi, Database, 
  AlertTriangle, CheckCircle, TrendingUp, Gauge
} from 'lucide-react';

interface Node {
  id: string;
  name: string;
  type: 'gpu' | 'api' | 'worker' | 'database' | 'cache';
  status: 'healthy' | 'warning' | 'critical' | 'offline';
  metrics: { cpu: number; memory: number; disk: number; network: number };
  location: string;
  uptime: string;
}

const mockNodes: Node[] = [
  { id: '1', name: 'gpu-node-01', type: 'gpu', status: 'healthy', metrics: { cpu: 78, memory: 85, disk: 45, network: 234 }, location: 'us-west-2a', uptime: '45d 12h' },
  { id: '2', name: 'gpu-node-02', type: 'gpu', status: 'healthy', metrics: { cpu: 65, memory: 72, disk: 38, network: 198 }, location: 'us-west-2b', uptime: '45d 12h' },
  { id: '3', name: 'api-server-01', type: 'api', status: 'healthy', metrics: { cpu: 34, memory: 56, disk: 22, network: 1240 }, location: 'us-west-2a', uptime: '90d 4h' },
  { id: '4', name: 'api-server-02', type: 'api', status: 'warning', metrics: { cpu: 89, memory: 78, disk: 56, network: 1890 }, location: 'us-west-2b', uptime: '90d 4h' },
  { id: '5', name: 'worker-pool-01', type: 'worker', status: 'healthy', metrics: { cpu: 45, memory: 62, disk: 34, network: 456 }, location: 'us-west-2a', uptime: '30d 8h' },
  { id: '6', name: 'postgres-primary', type: 'database', status: 'healthy', metrics: { cpu: 28, memory: 45, disk: 67, network: 234 }, location: 'us-west-2a', uptime: '120d 2h' },
  { id: '7', name: 'redis-cluster', type: 'cache', status: 'healthy', metrics: { cpu: 12, memory: 78, disk: 15, network: 890 }, location: 'us-west-2a', uptime: '60d 14h' },
];

const statusConfig = {
  healthy: { color: 'text-emerald-500', bg: 'bg-emerald-500', bgLight: 'bg-emerald-500/10' },
  warning: { color: 'text-amber-500', bg: 'bg-amber-500', bgLight: 'bg-amber-500/10' },
  critical: { color: 'text-red-500', bg: 'bg-red-500', bgLight: 'bg-red-500/10' },
  offline: { color: 'text-slate-400', bg: 'bg-slate-400', bgLight: 'bg-slate-400/10' },
};

const typeIcons = {
  gpu: Cpu,
  api: Server,
  worker: Activity,
  database: Database,
  cache: HardDrive,
};

function MetricBar({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span>{value}%</span>
      </div>
      <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div 
          className={`h-full rounded-full ${color}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export function InfrastructurePage() {
  const healthy = mockNodes.filter(n => n.status === 'healthy').length;
  const warning = mockNodes.filter(n => n.status === 'warning').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Infrastructure</h2>
          <p className="text-slate-500 dark:text-slate-400">Monitor servers, GPUs, and services</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Total Nodes</p>
              <p className="text-2xl font-bold mt-1">{mockNodes.length}</p>
            </div>
            <Server className="text-slate-400" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Healthy</p>
              <p className="text-2xl font-bold mt-1 text-emerald-500">{healthy}</p>
            </div>
            <CheckCircle className="text-emerald-500" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Warnings</p>
              <p className="text-2xl font-bold mt-1 text-amber-500">{warning}</p>
            </div>
            <AlertTriangle className="text-amber-500" size={24} />
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Avg GPU Util</p>
              <p className="text-2xl font-bold mt-1">72%</p>
            </div>
            <Gauge className="text-cyan-500" size={24} />
          </div>
        </div>
      </div>

      {/* Nodes Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {mockNodes.map(node => {
          const TypeIcon = typeIcons[node.type];
          return (
            <div key={node.id} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${statusConfig[node.status].bgLight}`}>
                    <TypeIcon className={statusConfig[node.status].color} size={20} />
                  </div>
                  <div>
                    <p className="font-medium">{node.name}</p>
                    <p className="text-xs text-slate-500">{node.location}</p>
                  </div>
                </div>
                <div className={`w-2 h-2 rounded-full ${statusConfig[node.status].bg}`} />
              </div>

              <div className="space-y-3">
                <MetricBar 
                  value={node.metrics.cpu} 
                  label="CPU" 
                  color={node.metrics.cpu > 80 ? 'bg-red-500' : node.metrics.cpu > 60 ? 'bg-amber-500' : 'bg-emerald-500'} 
                />
                <MetricBar 
                  value={node.metrics.memory} 
                  label="Memory" 
                  color={node.metrics.memory > 80 ? 'bg-red-500' : node.metrics.memory > 60 ? 'bg-amber-500' : 'bg-emerald-500'} 
                />
                <MetricBar 
                  value={node.metrics.disk} 
                  label="Disk" 
                  color={node.metrics.disk > 80 ? 'bg-red-500' : node.metrics.disk > 60 ? 'bg-amber-500' : 'bg-cyan-500'} 
                />
              </div>

              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                <span className="text-xs text-slate-500">Uptime: {node.uptime}</span>
                <span className="text-xs text-slate-500">{node.metrics.network} Mb/s</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

