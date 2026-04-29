/**
 * Billing & Usage Page
 */
import React, { useState } from 'react';
import { 
  CreditCard, DollarSign, TrendingUp, Users, Zap,
  Download, Calendar, ChevronDown, ArrowUpRight, ArrowDownRight
} from 'lucide-react';

interface Invoice {
  id: string;
  tenant: string;
  amount: number;
  status: 'paid' | 'pending' | 'overdue';
  date: string;
  period: string;
}

interface UsageMetric {
  tenant: string;
  agentRuns: number;
  tokens: number;
  storage: number;
  premiumCalls: number;
  cost: number;
}

const mockInvoices: Invoice[] = [
  { id: 'INV-001', tenant: 'Acme Corp', amount: 4999, status: 'paid', date: 'Dec 1, 2025', period: 'November 2025' },
  { id: 'INV-002', tenant: 'FinanceX', amount: 4999, status: 'paid', date: 'Dec 1, 2025', period: 'November 2025' },
  { id: 'INV-003', tenant: 'TechStart', amount: 499, status: 'pending', date: 'Dec 1, 2025', period: 'November 2025' },
  { id: 'INV-004', tenant: 'HealthTech', amount: 499, status: 'paid', date: 'Dec 1, 2025', period: 'November 2025' },
  { id: 'INV-005', tenant: 'RetailCo', amount: 0, status: 'paid', date: 'Dec 1, 2025', period: 'November 2025 (Trial)' },
];

const mockUsage: UsageMetric[] = [
  { tenant: 'Acme Corp', agentRuns: 2340, tokens: 45000000, storage: 45, premiumCalls: 89, cost: 234.50 },
  { tenant: 'FinanceX', agentRuns: 1890, tokens: 38000000, storage: 89, premiumCalls: 156, cost: 312.80 },
  { tenant: 'TechStart', agentRuns: 456, tokens: 8900000, storage: 12, premiumCalls: 23, cost: 45.60 },
  { tenant: 'HealthTech', agentRuns: 234, tokens: 4500000, storage: 8, premiumCalls: 12, cost: 23.40 },
  { tenant: 'DataDriven', agentRuns: 890, tokens: 18000000, storage: 34, premiumCalls: 45, cost: 89.50 },
];

const statusColors = {
  paid: 'text-emerald-500 bg-emerald-500/10',
  pending: 'text-amber-500 bg-amber-500/10',
  overdue: 'text-red-500 bg-red-500/10',
};

export function BillingPage() {
  const [period, setPeriod] = useState('December 2025');

  const totalMRR = 15995;
  const totalUsageCost = mockUsage.reduce((sum, u) => sum + u.cost, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Billing & Usage</h2>
          <p className="text-slate-500 dark:text-slate-400">Revenue, invoices, and usage metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <select 
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
          >
            <option>December 2025</option>
            <option>November 2025</option>
            <option>October 2025</option>
          </select>
          <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800">
            <Download size={18} />
            Export
          </button>
        </div>
      </div>

      {/* Revenue Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">MRR</p>
              <p className="text-2xl font-bold mt-1">${totalMRR.toLocaleString()}</p>
            </div>
            <div className="flex items-center text-emerald-500 text-sm">
              <ArrowUpRight size={16} />
              +12%
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Usage Revenue</p>
              <p className="text-2xl font-bold mt-1">${totalUsageCost.toFixed(2)}</p>
            </div>
            <div className="flex items-center text-emerald-500 text-sm">
              <ArrowUpRight size={16} />
              +8%
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Paying Customers</p>
              <p className="text-2xl font-bold mt-1">42</p>
            </div>
            <div className="flex items-center text-emerald-500 text-sm">
              <ArrowUpRight size={16} />
              +5
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Cloud Costs</p>
              <p className="text-2xl font-bold mt-1">$892</p>
            </div>
            <div className="flex items-center text-red-500 text-sm">
              <ArrowDownRight size={16} />
              -15%
            </div>
          </div>
        </div>
      </div>

      {/* Usage Table */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="font-semibold">Usage by Tenant</h3>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-900/50">
            <tr className="text-left text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 font-medium">Tenant</th>
              <th className="py-3 px-4 font-medium">Agent Runs</th>
              <th className="py-3 px-4 font-medium">Tokens</th>
              <th className="py-3 px-4 font-medium">Storage (GB)</th>
              <th className="py-3 px-4 font-medium">Premium Calls</th>
              <th className="py-3 px-4 font-medium text-right">Usage Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {mockUsage.map(usage => (
              <tr key={usage.tenant} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="py-3 px-4 font-medium">{usage.tenant}</td>
                <td className="py-3 px-4">{usage.agentRuns.toLocaleString()}</td>
                <td className="py-3 px-4">{(usage.tokens / 1000000).toFixed(1)}M</td>
                <td className="py-3 px-4">{usage.storage}</td>
                <td className="py-3 px-4">{usage.premiumCalls}</td>
                <td className="py-3 px-4 text-right font-medium">${usage.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Invoices */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="font-semibold">Recent Invoices</h3>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-900/50">
            <tr className="text-left text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 font-medium">Invoice</th>
              <th className="py-3 px-4 font-medium">Tenant</th>
              <th className="py-3 px-4 font-medium">Period</th>
              <th className="py-3 px-4 font-medium">Status</th>
              <th className="py-3 px-4 font-medium text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {mockInvoices.map(invoice => (
              <tr key={invoice.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="py-3 px-4 font-mono text-sm">{invoice.id}</td>
                <td className="py-3 px-4 font-medium">{invoice.tenant}</td>
                <td className="py-3 px-4 text-sm text-slate-500">{invoice.period}</td>
                <td className="py-3 px-4">
                  <span className={`px-2 py-1 rounded-full text-xs capitalize ${statusColors[invoice.status]}`}>
                    {invoice.status}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-medium">
                  ${invoice.amount.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

