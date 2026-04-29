/**
 * Settings Page
 */
import React, { useState } from 'react';
import { 
  Settings, Bell, Shield, Database, Cpu, Globe, 
  Key, Mail, Save, RefreshCw, AlertTriangle
} from 'lucide-react';

interface SettingSection {
  id: string;
  title: string;
  icon: React.ReactNode;
}

const sections: SettingSection[] = [
  { id: 'general', title: 'General', icon: <Settings size={20} /> },
  { id: 'models', title: 'Model Config', icon: <Cpu size={20} /> },
  { id: 'security', title: 'Security', icon: <Shield size={20} /> },
  { id: 'notifications', title: 'Notifications', icon: <Bell size={20} /> },
  { id: 'api', title: 'API Keys', icon: <Key size={20} /> },
];

export function SettingsPage() {
  const [activeSection, setActiveSection] = useState('general');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Settings</h2>
          <p className="text-slate-500 dark:text-slate-400">Configure platform settings</p>
        </div>
        <button 
          onClick={handleSave}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            saved 
              ? 'bg-emerald-500 text-white' 
              : 'bg-cyan-500 text-white hover:bg-cyan-600'
          }`}
        >
          {saved ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
          {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-64 space-y-1">
          {sections.map(section => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                activeSection === section.id
                  ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {section.icon}
              <span className="text-sm font-medium">{section.title}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
          {activeSection === 'general' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">General Settings</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Platform Name</label>
                  <input 
                    type="text" 
                    defaultValue="code4u.ai"
                    className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:ring-2 focus:ring-cyan-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Admin Email</label>
                  <input 
                    type="email" 
                    defaultValue="admin@code4u.ai"
                    className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:ring-2 focus:ring-cyan-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Default Timezone</label>
                  <select className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900">
                    <option>UTC</option>
                    <option>America/New_York</option>
                    <option>America/Los_Angeles</option>
                    <option>Europe/London</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'models' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Model Configuration</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Default Self-Hosted Model</label>
                  <select className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900">
                    <option>DeepSeek Coder V2</option>
                    <option>CodeLlama 70B</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Max Retry Attempts</label>
                  <input 
                    type="number" 
                    defaultValue={2}
                    className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900"
                  />
                </div>
                <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                  <div>
                    <p className="font-medium">Enable Premium Fallback</p>
                    <p className="text-sm text-slate-500">Fall back to GPT-4o/Claude after retries</p>
                  </div>
                  <button className="w-12 h-6 bg-cyan-500 rounded-full p-1">
                    <div className="w-4 h-4 bg-white rounded-full ml-auto" />
                  </button>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Daily Token Cap</label>
                  <input 
                    type="number" 
                    defaultValue={10000000}
                    className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900"
                  />
                </div>
              </div>
            </div>
          )}

          {activeSection === 'security' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Security Settings</h3>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                  <div>
                    <p className="font-medium">Require mTLS</p>
                    <p className="text-sm text-slate-500">Enforce mutual TLS for all connections</p>
                  </div>
                  <button className="w-12 h-6 bg-cyan-500 rounded-full p-1">
                    <div className="w-4 h-4 bg-white rounded-full ml-auto" />
                  </button>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                  <div>
                    <p className="font-medium">Enable Audit Logging</p>
                    <p className="text-sm text-slate-500">Log all agent actions and file changes</p>
                  </div>
                  <button className="w-12 h-6 bg-cyan-500 rounded-full p-1">
                    <div className="w-4 h-4 bg-white rounded-full ml-auto" />
                  </button>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                  <div>
                    <p className="font-medium">PII Redaction</p>
                    <p className="text-sm text-slate-500">Automatically redact PII in logs</p>
                  </div>
                  <button className="w-12 h-6 bg-cyan-500 rounded-full p-1">
                    <div className="w-4 h-4 bg-white rounded-full ml-auto" />
                  </button>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Session Timeout (minutes)</label>
                  <input 
                    type="number" 
                    defaultValue={60}
                    className="w-full px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900"
                  />
                </div>
              </div>
            </div>
          )}

          {activeSection === 'notifications' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Notification Settings</h3>
              
              <div className="space-y-4">
                {[
                  { title: 'Agent Failures', desc: 'Notify when agent runs fail' },
                  { title: 'High Usage Alerts', desc: 'Alert when usage exceeds thresholds' },
                  { title: 'Security Events', desc: 'Notify on blocked actions and violations' },
                  { title: 'System Health', desc: 'Alert on infrastructure issues' },
                  { title: 'New Tenant Signups', desc: 'Notify when new tenants register' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                    <div>
                      <p className="font-medium">{item.title}</p>
                      <p className="text-sm text-slate-500">{item.desc}</p>
                    </div>
                    <button className="w-12 h-6 bg-cyan-500 rounded-full p-1">
                      <div className="w-4 h-4 bg-white rounded-full ml-auto" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'api' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">API Keys</h3>
              
              <div className="space-y-4">
                <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start gap-3">
                  <AlertTriangle className="text-amber-500 mt-0.5" size={20} />
                  <div>
                    <p className="font-medium text-amber-700 dark:text-amber-400">Keep your API keys secure</p>
                    <p className="text-sm text-amber-600 dark:text-amber-500">Never share or expose these keys publicly.</p>
                  </div>
                </div>

                {[
                  { name: 'OpenAI API Key', key: 'sk-****************************X7mK', status: 'active' },
                  { name: 'Anthropic API Key', key: 'sk-ant-****************************9d3f', status: 'active' },
                  { name: 'Google AI API Key', key: 'AIza****************************8xYz', status: 'inactive' },
                ].map((api, i) => (
                  <div key={i} className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700">
                    <div>
                      <p className="font-medium">{api.name}</p>
                      <p className="text-sm font-mono text-slate-500">{api.key}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        api.status === 'active' 
                          ? 'bg-emerald-500/10 text-emerald-500' 
                          : 'bg-slate-500/10 text-slate-500'
                      }`}>
                        {api.status}
                      </span>
                      <button className="text-sm text-cyan-500 hover:text-cyan-600">Edit</button>
                    </div>
                  </div>
                ))}

                <button className="w-full py-2 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg text-slate-500 hover:border-cyan-500 hover:text-cyan-500 transition-colors">
                  + Add API Key
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

