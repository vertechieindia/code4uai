/**
 * Security & Compliance Page
 */
import React, { useState } from 'react';
import { 
  Shield, Lock, Key, AlertTriangle, CheckCircle, Eye, 
  FileText, Users, Clock, ExternalLink, XCircle
} from 'lucide-react';

interface AuditLog {
  id: string;
  action: string;
  actor: string;
  tenant: string;
  resource: string;
  timestamp: string;
  status: 'success' | 'warning' | 'blocked';
}

interface NoAIZone {
  id: string;
  path: string;
  reason: string;
  tenant: string;
  createdBy: string;
}

const mockAuditLogs: AuditLog[] = [
  { id: '1', action: 'agent.execute', actor: 'user@acme.com', tenant: 'Acme Corp', resource: 'src/auth/login.ts', timestamp: '2 min ago', status: 'success' },
  { id: '2', action: 'file.modify', actor: 'agent', tenant: 'TechStart', resource: 'api/routes/users.py', timestamp: '5 min ago', status: 'success' },
  { id: '3', action: 'zone.blocked', actor: 'agent', tenant: 'FinanceX', resource: 'src/payments/stripe.ts', timestamp: '8 min ago', status: 'blocked' },
  { id: '4', action: 'tenant.settings', actor: 'admin@financex.com', tenant: 'FinanceX', resource: 'tenant.settings', timestamp: '15 min ago', status: 'success' },
  { id: '5', action: 'agent.execute', actor: 'dev@healthtech.com', tenant: 'HealthTech', resource: 'src/api/patients.ts', timestamp: '20 min ago', status: 'warning' },
  { id: '6', action: 'ownership.override', actor: 'admin@acme.com', tenant: 'Acme Corp', resource: 'CODEOWNERS', timestamp: '1 hour ago', status: 'success' },
];

const mockNoAIZones: NoAIZone[] = [
  { id: '1', path: 'src/auth/**', reason: 'Authentication logic - security sensitive', tenant: 'All', createdBy: 'System' },
  { id: '2', path: 'src/payments/**', reason: 'Payment processing - PCI compliance', tenant: 'All', createdBy: 'System' },
  { id: '3', path: 'src/crypto/**', reason: 'Cryptographic operations', tenant: 'All', createdBy: 'System' },
  { id: '4', path: 'config/secrets/**', reason: 'Secret management', tenant: 'All', createdBy: 'System' },
  { id: '5', path: 'src/compliance/hipaa/**', reason: 'HIPAA compliance code', tenant: 'HealthTech', createdBy: 'admin@healthtech.com' },
];

const statusConfig = {
  success: { color: 'text-emerald-500 bg-emerald-500/10', icon: CheckCircle },
  warning: { color: 'text-amber-500 bg-amber-500/10', icon: AlertTriangle },
  blocked: { color: 'text-red-500 bg-red-500/10', icon: XCircle },
};

export function SecurityPage() {
  const [activeTab, setActiveTab] = useState<'audit' | 'zones' | 'compliance'>('audit');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Security & Compliance</h2>
          <p className="text-slate-500 dark:text-slate-400">Audit logs, No-AI zones, and compliance status</p>
        </div>
      </div>

      {/* Compliance Badges */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <Shield className="text-emerald-500" size={20} />
            </div>
            <div>
              <p className="font-medium">SOC 2 Type II</p>
              <p className="text-xs text-emerald-500">Compliant</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <Lock className="text-emerald-500" size={20} />
            </div>
            <div>
              <p className="font-medium">ISO 27001</p>
              <p className="text-xs text-emerald-500">Certified</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <FileText className="text-emerald-500" size={20} />
            </div>
            <div>
              <p className="font-medium">GDPR</p>
              <p className="text-xs text-emerald-500">Compliant</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/10 rounded-lg">
              <Key className="text-cyan-500" size={20} />
            </div>
            <div>
              <p className="font-medium">mTLS</p>
              <p className="text-xs text-cyan-500">Enabled</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200 dark:border-slate-700">
        <button 
          onClick={() => setActiveTab('audit')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'audit' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Audit Logs
        </button>
        <button 
          onClick={() => setActiveTab('zones')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'zones' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          No-AI Zones
        </button>
        <button 
          onClick={() => setActiveTab('compliance')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'compliance' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Compliance Controls
        </button>
      </div>

      {/* Audit Logs Tab */}
      {activeTab === 'audit' && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
            <h3 className="font-semibold">Recent Activity</h3>
            <button className="text-sm text-cyan-500 hover:text-cyan-600">Export Logs</button>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {mockAuditLogs.map(log => {
              const StatusIcon = statusConfig[log.status].icon;
              return (
                <div key={log.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${statusConfig[log.status].color}`}>
                        <StatusIcon size={16} />
                      </div>
                      <div>
                        <p className="font-medium">{log.action}</p>
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <span>{log.actor}</span>
                          <span>•</span>
                          <span>{log.tenant}</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-mono text-slate-600 dark:text-slate-400">{log.resource}</p>
                      <p className="text-xs text-slate-500">{log.timestamp}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No-AI Zones Tab */}
      {activeTab === 'zones' && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
            <h3 className="font-semibold">Protected Paths</h3>
            <button className="px-3 py-1.5 bg-cyan-500 text-white text-sm rounded-lg hover:bg-cyan-600">
              Add Zone
            </button>
          </div>
          <table className="w-full">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 uppercase">
                <th className="py-3 px-4 font-medium">Path Pattern</th>
                <th className="py-3 px-4 font-medium">Reason</th>
                <th className="py-3 px-4 font-medium">Tenant</th>
                <th className="py-3 px-4 font-medium">Created By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {mockNoAIZones.map(zone => (
                <tr key={zone.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="py-3 px-4 font-mono text-sm text-red-600 dark:text-red-400">{zone.path}</td>
                  <td className="py-3 px-4 text-sm">{zone.reason}</td>
                  <td className="py-3 px-4 text-sm">{zone.tenant}</td>
                  <td className="py-3 px-4 text-sm text-slate-500">{zone.createdBy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Compliance Controls Tab */}
      {activeTab === 'compliance' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            { title: 'Tenant Isolation', status: 'active', desc: 'Separate Knowledge Graph, embeddings, and storage per tenant' },
            { title: 'mTLS Enforcement', status: 'active', desc: 'Mutual TLS between all services' },
            { title: 'RBAC on Intents', status: 'active', desc: 'Role-based access control for agent actions' },
            { title: 'Signed Diffs', status: 'active', desc: 'Cryptographic signing of all code changes' },
            { title: 'Immutable Audit Logs', status: 'active', desc: 'Tamper-proof logging of all operations' },
            { title: 'PII Redaction', status: 'active', desc: 'Automatic redaction in logs and outputs' },
            { title: 'Data Retention Policy', status: 'active', desc: '90-day retention with secure deletion' },
            { title: 'Encryption at Rest', status: 'active', desc: 'AES-256 encryption for all stored data' },
          ].map((control, i) => (
            <div key={i} className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm flex items-start gap-4">
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <CheckCircle className="text-emerald-500" size={20} />
              </div>
              <div>
                <p className="font-medium">{control.title}</p>
                <p className="text-sm text-slate-500 mt-1">{control.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

