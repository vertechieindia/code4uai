/**
 * code4u.ai Web Agent Manager
 * Full web interface for managing AI coding agents
 */
import React, { useState, useEffect } from 'react';
import { 
  GitBranch, Send, Paperclip, Mic, Settings, User, 
  MessageSquare, Code, FileCode, FolderOpen, CheckCircle,
  XCircle, Loader, Clock, ChevronRight, Plus, Search,
  MoreVertical, ExternalLink, RefreshCw, Zap, Brain,
  Terminal, Eye, RotateCcw, Play, Pause, ArrowRight
} from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  state?: string;
  files?: string[];
}

interface AgentSession {
  id: string;
  name: string;
  status: 'active' | 'idle' | 'completed';
  task: string;
  state: string;
  startTime: Date;
}

const mockSessions: AgentSession[] = [
  { id: '1', name: 'Refactor Auth', status: 'active', task: 'Rename email to primaryEmail', state: 'CODE_GENERATED', startTime: new Date() },
  { id: '2', name: 'Add API Endpoint', status: 'idle', task: 'Create user preferences API', state: 'READY_FOR_REVIEW', startTime: new Date() },
  { id: '3', name: 'Fix Bug #432', status: 'completed', task: 'Fix validation error in checkout', state: 'APPLIED', startTime: new Date() },
];

const mockMessages: ChatMessage[] = [
  { id: '1', role: 'user', content: 'Rename the email field to primaryEmail across all services', timestamp: new Date(Date.now() - 60000) },
  { id: '2', role: 'system', content: '🔍 Analyzing Knowledge Graph...', timestamp: new Date(Date.now() - 55000), state: 'IMPACT_ANALYZED' },
  { id: '3', role: 'agent', content: 'I found 8 files across 3 services that reference the `email` field:\n\n• `UserSchema` in `schemas/user.py`\n• `UserModel` in `models/user.py`\n• `ProfileAPI` in `api/profile.py`\n• Plus 5 more files\n\nThis is a **breaking change** that will affect the public API. I will generate a migration plan.', timestamp: new Date(Date.now() - 50000), state: 'PLAN_GENERATED', files: ['schemas/user.py', 'models/user.py', 'api/profile.py'] },
  { id: '4', role: 'system', content: '✅ Contract validated. No conflicts detected.', timestamp: new Date(Date.now() - 45000), state: 'CONTRACT_VALIDATED' },
  { id: '5', role: 'agent', content: 'I\'ve generated the changes. Here\'s a summary:\n\n```diff\n- email: str\n+ primaryEmail: str\n```\n\n8 files modified, 47 lines changed.\n\nReady for your review.', timestamp: new Date(Date.now() - 40000), state: 'READY_FOR_REVIEW' },
];

const stateColors: Record<string, string> = {
  INIT: 'text-slate-400',
  IMPACT_ANALYZED: 'text-blue-400',
  PLAN_GENERATED: 'text-purple-400',
  CONTRACT_VALIDATED: 'text-cyan-400',
  CODE_GENERATED: 'text-amber-400',
  VERIFIED: 'text-emerald-400',
  READY_FOR_REVIEW: 'text-orange-400',
  APPLIED: 'text-green-400',
  FAILED: 'text-red-400',
};

function ChatMessage({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-full text-sm text-slate-400">
          {message.state && (
            <span className={`font-medium ${stateColors[message.state]}`}>
              [{message.state}]
            </span>
          )}
          <span>{message.content}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? 'bg-gradient-to-br from-cyan-500 to-emerald-500' : 'bg-gradient-to-br from-purple-500 to-pink-500'
      }`}>
        {isUser ? <User size={16} className="text-white" /> : <Brain size={16} className="text-white" />}
      </div>
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block px-4 py-3 rounded-2xl ${
          isUser 
            ? 'bg-cyan-500 text-white rounded-tr-sm' 
            : 'bg-slate-800 text-white rounded-tl-sm'
        }`}>
          <pre className="whitespace-pre-wrap font-sans text-sm">{message.content}</pre>
          {message.files && message.files.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <p className="text-xs opacity-70 mb-2">Files affected:</p>
              <div className="flex flex-wrap gap-1">
                {message.files.map((file, i) => (
                  <span key={i} className="px-2 py-1 bg-white/10 rounded text-xs font-mono">
                    {file}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {message.timestamp.toLocaleTimeString()}
          {message.state && (
            <span className={`ml-2 ${stateColors[message.state]}`}>• {message.state}</span>
          )}
        </p>
      </div>
    </div>
  );
}

function SessionCard({ session, active, onClick }: { session: AgentSession; active: boolean; onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full text-left p-4 rounded-xl transition-all ${
        active 
          ? 'bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 border border-cyan-500/50' 
          : 'bg-slate-800/50 hover:bg-slate-800 border border-transparent'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="font-medium text-white">{session.name}</span>
        <span className={`w-2 h-2 rounded-full ${
          session.status === 'active' ? 'bg-cyan-500 animate-pulse' :
          session.status === 'idle' ? 'bg-amber-500' : 'bg-emerald-500'
        }`} />
      </div>
      <p className="text-sm text-slate-400 line-clamp-1">{session.task}</p>
      <div className="flex items-center gap-2 mt-2">
        <span className={`text-xs px-2 py-0.5 rounded-full ${stateColors[session.state]} bg-current/10`}>
          {session.state}
        </span>
      </div>
    </button>
  );
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(mockMessages);
  const [input, setInput] = useState('');
  const [sessions, setSessions] = useState(mockSessions);
  const [activeSession, setActiveSession] = useState(mockSessions[0].id);
  const [isThinking, setIsThinking] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;
    
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    
    setMessages([...messages, newMessage]);
    setInput('');
    setIsThinking(true);

    // Simulate agent response
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: '🔍 Analyzing request...',
        timestamp: new Date(),
        state: 'IMPACT_ANALYZED'
      }]);
    }, 1000);

    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'agent',
        content: 'I understand. Let me analyze the codebase and prepare a plan for this change.',
        timestamp: new Date(),
        state: 'PLAN_GENERATED'
      }]);
      setIsThinking(false);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white flex">
      {/* Sidebar */}
      <aside className="w-80 border-r border-slate-800 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center">
              <Zap size={20} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg">code4u.ai</h1>
              <p className="text-xs text-slate-400">Agent Manager</p>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="p-4">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search sessions..."
              className="w-full pl-10 pr-4 py-2 bg-slate-800/50 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>
        </div>

        {/* New Session Button */}
        <div className="px-4 mb-4">
          <button className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-lg font-medium hover:opacity-90 transition-opacity">
            <Plus size={18} />
            New Agent Session
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto px-4 space-y-2">
          <p className="text-xs font-medium text-slate-500 uppercase mb-2">Active Sessions</p>
          {sessions.filter(s => s.status === 'active').map(session => (
            <SessionCard 
              key={session.id} 
              session={session} 
              active={activeSession === session.id}
              onClick={() => setActiveSession(session.id)}
            />
          ))}

          <p className="text-xs font-medium text-slate-500 uppercase mt-6 mb-2">Recent</p>
          {sessions.filter(s => s.status !== 'active').map(session => (
            <SessionCard 
              key={session.id} 
              session={session} 
              active={activeSession === session.id}
              onClick={() => setActiveSession(session.id)}
            />
          ))}
        </div>

        {/* User Profile */}
        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <span className="text-sm font-bold">JD</span>
            </div>
            <div className="flex-1">
              <p className="font-medium text-sm">John Doe</p>
              <p className="text-xs text-slate-400">john@acme.com</p>
            </div>
            <button className="p-2 hover:bg-slate-800 rounded-lg">
              <Settings size={18} className="text-slate-400" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <h2 className="font-semibold">Refactor Auth</h2>
            <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded-full">
              Active
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm">
              <Eye size={16} />
              View Diff
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm">
              <Terminal size={16} />
              Terminal
            </button>
            <button className="p-2 hover:bg-slate-800 rounded-lg">
              <MoreVertical size={18} className="text-slate-400" />
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map(message => (
            <ChatMessage key={message.id} message={message} />
          ))}
          
          {isThinking && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Brain size={16} className="text-white" />
              </div>
              <div className="px-4 py-3 bg-slate-800 rounded-2xl rounded-tl-sm">
                <div className="flex items-center gap-2">
                  <Loader size={14} className="animate-spin text-cyan-400" />
                  <span className="text-sm text-slate-400">Agent is thinking...</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* State Timeline */}
        <div className="border-t border-slate-800 px-6 py-3">
          <div className="flex items-center gap-2 overflow-x-auto">
            {['INIT', 'IMPACT_ANALYZED', 'PLAN_GENERATED', 'CONTRACT_VALIDATED', 'CODE_GENERATED', 'VERIFIED', 'READY_FOR_REVIEW'].map((state, i) => (
              <React.Fragment key={state}>
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs whitespace-nowrap ${
                  i <= 4 
                    ? 'bg-emerald-500/20 text-emerald-400' 
                    : i === 5 
                    ? 'bg-cyan-500/20 text-cyan-400 ring-2 ring-cyan-500/50' 
                    : 'bg-slate-800 text-slate-500'
                }`}>
                  {i <= 4 ? <CheckCircle size={12} /> : i === 5 ? <Loader size={12} className="animate-spin" /> : <Clock size={12} />}
                  {state.replace(/_/g, ' ')}
                </div>
                {i < 6 && <ArrowRight size={14} className="text-slate-600" />}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Action Buttons (for READY_FOR_REVIEW state) */}
        <div className="border-t border-slate-800 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <span>8 files changed</span>
            <span>47 lines</span>
            <span className="text-amber-400">Breaking change</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30">
              <XCircle size={16} />
              Reject
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600">
              <CheckCircle size={16} />
              Approve & Apply
            </button>
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-800 p-4">
          <div className="flex items-end gap-3">
            <button className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
              <Paperclip size={20} />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Describe what you want the agent to do..."
                className="w-full px-4 py-3 bg-slate-800/50 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500/50 min-h-[52px] max-h-32"
                rows={1}
              />
            </div>
            <button className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
              <Mic size={20} />
            </button>
            <button 
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-3 bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </main>

      {/* Right Panel - File Explorer / Diff View */}
      <aside className="w-80 border-l border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-semibold">Changed Files</h3>
          <button className="p-1.5 hover:bg-slate-800 rounded">
            <RefreshCw size={14} className="text-slate-400" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {[
            { path: 'schemas/user.py', additions: 5, deletions: 5 },
            { path: 'models/user.py', additions: 8, deletions: 8 },
            { path: 'api/profile.py', additions: 12, deletions: 6 },
            { path: 'api/routes/users.py', additions: 15, deletions: 12 },
            { path: 'tests/test_user.py', additions: 42, deletions: 0 },
          ].map((file, i) => (
            <button 
              key={i}
              className="w-full flex items-center gap-3 p-3 bg-slate-800/50 hover:bg-slate-800 rounded-lg text-left"
            >
              <FileCode size={16} className="text-cyan-400" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-mono truncate">{file.path}</p>
                <div className="flex items-center gap-2 text-xs mt-1">
                  <span className="text-emerald-400">+{file.additions}</span>
                  <span className="text-red-400">-{file.deletions}</span>
                </div>
              </div>
              <ChevronRight size={14} className="text-slate-500" />
            </button>
          ))}
        </div>

        {/* Quick Stats */}
        <div className="p-4 border-t border-slate-800">
          <h4 className="text-xs font-medium text-slate-500 uppercase mb-3">Session Stats</h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-lg font-bold">12s</p>
              <p className="text-xs text-slate-400">Duration</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-lg font-bold">4,520</p>
              <p className="text-xs text-slate-400">Tokens</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-lg font-bold">Self</p>
              <p className="text-xs text-slate-400">Model</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-lg font-bold text-emerald-400">0</p>
              <p className="text-xs text-slate-400">Retries</p>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

