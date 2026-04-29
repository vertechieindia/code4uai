/**
 * Sidebar Component
 */
import React from 'react';
import { 
  LayoutDashboard, Users, Settings, Server, Shield, CreditCard, 
  GitBranch, Cpu, BarChart3, LogOut, Store, Brain, Smartphone
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
}

export const navItems: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={20} /> },
  { id: 'tenants', label: 'Tenants', icon: <Users size={20} /> },
  { id: 'models', label: 'Models', icon: <Cpu size={20} /> },
  { id: 'agents', label: 'Agent Runs', icon: <GitBranch size={20} />, badge: '12' },
  { id: 'mcp', label: 'MCP Marketplace', icon: <Store size={20} /> },
  { id: 'knowledge', label: 'Knowledge', icon: <Brain size={20} /> },
  { id: 'infrastructure', label: 'Infrastructure', icon: <Server size={20} /> },
  { id: 'security', label: 'Security', icon: <Shield size={20} /> },
  { id: 'billing', label: 'Billing', icon: <CreditCard size={20} /> },
  { id: 'analytics', label: 'Analytics', icon: <BarChart3 size={20} /> },
  { id: 'mobile', label: 'Mobile Manager', icon: <Smartphone size={20} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
];

interface SidebarProps {
  activeItem: string;
  setActiveItem: (id: string) => void;
}

export function Sidebar({ activeItem, setActiveItem }: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col">
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <img src="/logo.png" alt="code4u.ai" className="w-8 h-8 rounded-lg" />
          code4u.ai
        </h1>
        <p className="text-xs text-slate-400 mt-1">Admin Dashboard</p>
      </div>
      
      <nav className="flex-1 p-4 overflow-y-auto">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setActiveItem(item.id)}
                className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg transition-colors ${
                  activeItem === item.id
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3">
                  {item.icon}
                  <span className="text-sm">{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-2 py-0.5 text-xs bg-cyan-500 text-white rounded-full">
                    {item.badge}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      
      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500" />
          <div className="flex-1">
            <p className="text-sm font-medium">Admin User</p>
            <p className="text-xs text-slate-400">admin@code4u.ai</p>
          </div>
          <button className="text-slate-400 hover:text-white">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}

