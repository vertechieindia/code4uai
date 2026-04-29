/**
 * Mobile / Web Agent Manager Page
 */
import React, { useState } from 'react';
import { 
  Smartphone, Monitor, Clock, CheckCircle, XCircle, Play,
  Pause, Eye, RefreshCw, Bell, User, Zap, MapPin
} from 'lucide-react';

interface Session {
  id: string;
  userId: string;
  platform: 'ios' | 'android' | 'web';
  device: string;
  status: 'active' | 'idle' | 'disconnected';
  currentTask: string | null;
  location: string;
  lastActivity: string;
  tasks: number;
}

interface Notification {
  id: string;
  type: 'task_complete' | 'approval_needed' | 'error' | 'info';
  message: string;
  userId: string;
  platform: 'push' | 'sms' | 'email';
  status: 'sent' | 'pending' | 'failed';
  timestamp: string;
}

const mockSessions: Session[] = [
  { id: '1', userId: 'john@acme.com', platform: 'ios', device: 'iPhone 15 Pro', status: 'active', currentTask: 'Refactor auth module', location: 'San Francisco, CA', lastActivity: 'Just now', tasks: 5 },
  { id: '2', userId: 'sarah@techstart.io', platform: 'web', device: 'Chrome on MacOS', status: 'active', currentTask: null, location: 'New York, NY', lastActivity: '2 min ago', tasks: 3 },
  { id: '3', userId: 'mike@financex.com', platform: 'android', device: 'Pixel 8', status: 'idle', currentTask: null, location: 'Chicago, IL', lastActivity: '15 min ago', tasks: 8 },
  { id: '4', userId: 'lisa@healthtech.com', platform: 'web', device: 'Firefox on Windows', status: 'active', currentTask: 'Add API endpoint', location: 'Austin, TX', lastActivity: '1 min ago', tasks: 2 },
  { id: '5', userId: 'david@datadriven.ai', platform: 'ios', device: 'iPad Pro', status: 'disconnected', currentTask: null, location: 'Seattle, WA', lastActivity: '1 hour ago', tasks: 12 },
];

const mockNotifications: Notification[] = [
  { id: '1', type: 'task_complete', message: 'Agent completed: Refactor auth module', userId: 'john@acme.com', platform: 'push', status: 'sent', timestamp: '2 min ago' },
  { id: '2', type: 'approval_needed', message: 'Review required for 3 file changes', userId: 'sarah@techstart.io', platform: 'push', status: 'sent', timestamp: '5 min ago' },
  { id: '3', type: 'error', message: 'Agent failed: Unable to parse requirements', userId: 'mike@financex.com', platform: 'push', status: 'sent', timestamp: '10 min ago' },
  { id: '4', type: 'info', message: 'New MCP server available: Playwright', userId: 'all', platform: 'email', status: 'pending', timestamp: '1 hour ago' },
];

const platformIcons = {
  ios: '🍎',
  android: '🤖',
  web: '🌐',
};

const statusConfig = {
  active: { color: 'bg-emerald-500', label: 'Active' },
  idle: { color: 'bg-amber-500', label: 'Idle' },
  disconnected: { color: 'bg-slate-400', label: 'Disconnected' },
};

const notificationTypeConfig = {
  task_complete: { color: 'text-emerald-500 bg-emerald-500/10', icon: CheckCircle },
  approval_needed: { color: 'text-amber-500 bg-amber-500/10', icon: Eye },
  error: { color: 'text-red-500 bg-red-500/10', icon: XCircle },
  info: { color: 'text-blue-500 bg-blue-500/10', icon: Bell },
};

export function MobilePage() {
  const [activeTab, setActiveTab] = useState<'sessions' | 'notifications'>('sessions');

  const activeSessions = mockSessions.filter(s => s.status === 'active').length;
  const totalTasks = mockSessions.reduce((s, sess) => s + sess.tasks, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Agent Manager</h2>
          <p className="text-slate-500 dark:text-slate-400">Mobile & Web sessions and notifications</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800">
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <Smartphone className="text-emerald-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Active Sessions</p>
              <p className="text-xl font-bold">{activeSessions}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/10 rounded-lg">
              <User className="text-cyan-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Total Users</p>
              <p className="text-xl font-bold">{mockSessions.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Zap className="text-purple-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Tasks Today</p>
              <p className="text-xl font-bold">{totalTasks}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <Bell className="text-amber-500" size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Notifications</p>
              <p className="text-xl font-bold">{mockNotifications.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200 dark:border-slate-700">
        <button 
          onClick={() => setActiveTab('sessions')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'sessions' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Active Sessions
        </button>
        <button 
          onClick={() => setActiveTab('notifications')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'notifications' 
              ? 'border-cyan-500 text-cyan-500' 
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Notifications
        </button>
      </div>

      {/* Sessions Tab */}
      {activeTab === 'sessions' && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 uppercase">
                <th className="py-3 px-4 font-medium">User</th>
                <th className="py-3 px-4 font-medium">Platform</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium">Current Task</th>
                <th className="py-3 px-4 font-medium">Location</th>
                <th className="py-3 px-4 font-medium">Last Activity</th>
                <th className="py-3 px-4 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {mockSessions.map(session => (
                <tr key={session.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                        {session.userId.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium">{session.userId}</p>
                        <p className="text-xs text-slate-500">{session.device}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-lg">{platformIcons[session.platform]}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${statusConfig[session.status].color}`} />
                      <span className="text-sm">{statusConfig[session.status].label}</span>
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {session.currentTask ? (
                      <span className="text-sm">{session.currentTask}</span>
                    ) : (
                      <span className="text-sm text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span className="flex items-center gap-1 text-sm text-slate-500">
                      <MapPin size={14} />
                      {session.location}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm text-slate-500">{session.lastActivity}</span>
                  </td>
                  <td className="py-3 px-4">
                    <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400">
                      <Eye size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {mockNotifications.map(notif => {
              const TypeIcon = notificationTypeConfig[notif.type].icon;
              return (
                <div key={notif.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className={`p-2 rounded-lg ${notificationTypeConfig[notif.type].color}`}>
                        <TypeIcon size={20} />
                      </div>
                      <div>
                        <p className="font-medium">{notif.message}</p>
                        <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
                          <span>{notif.userId}</span>
                          <span>•</span>
                          <span className="capitalize">{notif.platform}</span>
                          <span>•</span>
                          <span>{notif.timestamp}</span>
                        </div>
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs capitalize ${
                      notif.status === 'sent' ? 'bg-emerald-500/10 text-emerald-500' :
                      notif.status === 'pending' ? 'bg-amber-500/10 text-amber-500' :
                      'bg-red-500/10 text-red-500'
                    }`}>
                      {notif.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

