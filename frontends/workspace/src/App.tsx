import { useState, useEffect, createContext, useContext } from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AuthProvider, useAuth, RequireAuth } from './AuthContext'
import CommandPalette from './components/CommandPalette'
import { 
  Search, 
  Settings, 
  Bell, 
  RefreshCw,
  X,
  CheckCircle,
  AlertTriangle,
  Info,
  User,
  LogOut,
  Key,
  Shield,
  CreditCard,
  Sun,
  Moon,
  Monitor,
} from 'lucide-react'
import IDE from './IDE'
import {
  DashboardPage,
  ProjectsPage,
  AgentPage,
  ConnectRepoPage,
  RefactorPage,
  TutorialsPage,
  DocsPage,
  NewProjectPage,
  ExtensionsPage,
  IntegrationsPage,
  LoginPage,
  SignupPage,
  SecurityPage,
  GuardianPage,
  OrgDashboard,
} from './pages'

// Theme types
type ThemeMode = 'dark' | 'light' | 'system'

interface ThemeContextType {
  darkMode: boolean
  setDarkMode: (v: boolean) => void
  themeMode: ThemeMode
  setThemeMode: (m: ThemeMode) => void
}

const DarkModeContext = createContext<ThemeContextType>({
  darkMode: true,
  setDarkMode: () => {},
  themeMode: 'dark',
  setThemeMode: () => {},
})

export const useDarkMode = () => useContext(DarkModeContext)

// Page transition variants
const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] as const } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15, ease: [0.42, 0, 1, 1] as const } },
}

// Notification types
interface Notification {
  id: string
  type: 'success' | 'warning' | 'info'
  title: string
  message: string
  time: string
  read: boolean
}

const mockNotifications: Notification[] = [
  { id: '1', type: 'success', title: 'Build Completed', message: 'Your project built successfully', time: '2 min ago', read: false },
  { id: '2', type: 'info', title: 'New Feature', message: 'AI Agent now supports multi-file editing', time: '1 hour ago', read: false },
  { id: '3', type: 'warning', title: 'Usage Alert', message: 'You have used 80% of your monthly quota', time: '2 hours ago', read: true },
  { id: '4', type: 'success', title: 'Agent Task Done', message: 'Refactoring task completed', time: '5 hours ago', read: true },
]

// ---------------------------------------------------------------------------
// Onboarding Tour — with element spotlight highlighting
// ---------------------------------------------------------------------------
interface TourStep {
  title: string
  description: string
  action: string
  path: string
  target?: string
}

const tourSteps: TourStep[] = [
  {
    title: 'Welcome to code4u.ai',
    description: 'Your AI-native engineering platform that doesn\'t just generate code — it executes verified engineering changes. Let\'s walk through everything.',
    action: 'Let\'s Go',
    path: '/',
    target: '[data-tour="logo"]',
  },
  {
    title: 'Navigation Bar',
    description: 'Use the top navigation to move between pages. Dashboard, Projects, AI Agent, Security, Integrations, and Docs are all one click away.',
    action: 'Next',
    path: '/',
    target: '[data-tour="nav"]',
  },
  {
    title: 'Dashboard — Your Command Center',
    description: 'The Dashboard shows project health scores, recent activity, cloud costs, and token usage at a glance. Use the quick-start cards to jump into any workflow.',
    action: 'Next',
    path: '/',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Search & Command Palette',
    description: 'Click here or press Cmd+K to open the command palette. Search files, symbols, jump to any page, or trigger actions instantly.',
    action: 'Next',
    path: '/',
    target: '[data-tour="search"]',
  },
  {
    title: 'Projects — Manage Your Codebase',
    description: 'View all your indexed projects, their health scores, language distribution, and complexity heatmaps. Click any project to open it in the IDE.',
    action: 'Next',
    path: '/projects',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Connect a Repository',
    description: 'Link a GitHub, GitLab, or local repository. The AI automatically indexes every file, function, and class into a searchable Knowledge Graph.',
    action: 'Next',
    path: '/connect-repo',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'The IDE — Code Editor',
    description: 'A full Monaco-powered editor with syntax highlighting, multi-tab editing, and file tree navigation. This is where you read, write, and review code.',
    action: 'Next',
    path: '/ide',
  },
  {
    title: 'AI Agent — Swarm Orchestration',
    description: 'Give a high-level goal and the multi-agent swarm decomposes it into tasks. The Chief Architect plans, specialist agents execute, and the Heal agent auto-fixes failures.',
    action: 'Next',
    path: '/agent',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'AI Agent — Emergency Stop',
    description: 'The red EMERGENCY STOP button kills all running tasks instantly. Use it if a swarm is consuming too many tokens or stuck in a loop.',
    action: 'Next',
    path: '/agent',
    target: '[data-tour="emergency-stop"]',
  },
  {
    title: 'Security — Vulnerability Scanning',
    description: 'Automated scanning for secrets (AWS keys, tokens), SAST patterns (SQL injection, XSS), and known CVEs in your dependencies. Nothing unsafe gets through Sentinel.',
    action: 'Next',
    path: '/security',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Integrations — Connect Your Tools',
    description: 'Connect Slack, Jira, GitHub, Linear, and more. The AI posts summaries when swarm tasks complete, and can pull requirements from Zoom/Teams transcripts.',
    action: 'Next',
    path: '/integrations',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Settings — LLM & Models',
    description: 'Choose between cloud providers (OpenAI, Anthropic, Google) or local models (Ollama, vLLM). The Model Routing Table shows which model each agent type uses.',
    action: 'Next',
    path: '/settings',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Settings — System Diagnostics',
    description: 'The "System Status" tab runs health probes on PostgreSQL, Redis, LLM providers, Git, Vector Store, and disk space. Aim for a 100% readiness score.',
    action: 'Next',
    path: '/settings',
    target: '[data-tour="page-content"]',
  },
  {
    title: 'Profile & Account',
    description: 'Access your profile, API keys, billing, and logout from the avatar menu in the top-right corner.',
    action: 'Next',
    path: '/',
    target: '[data-tour="profile"]',
  },
  {
    title: 'Theme Switcher',
    description: 'Toggle between Dark, Light, and System themes using the moon/sun icon. Your preference is saved automatically.',
    action: 'Next',
    path: '/',
    target: '[data-tour="theme"]',
  },
  {
    title: 'You\'re Ready!',
    description: 'Start by connecting a repository, then try running /optimize in the IDE chat to find performance issues. The AI swarm is at your command. Happy engineering!',
    action: 'Start Building',
    path: '/',
    target: '[data-tour="page-content"]',
  },
]

function OnboardingTour({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0)
  const [spotlightRect, setSpotlightRect] = useState<DOMRect | null>(null)
  const navigate = useNavigate()
  const { darkMode } = useDarkMode()
  const current = tourSteps[step]

  useEffect(() => {
    const findTarget = () => {
      if (!current.target) { setSpotlightRect(null); return }
      const el = document.querySelector(current.target)
      if (el) {
        const rect = el.getBoundingClientRect()
        setSpotlightRect(rect)
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      } else {
        setSpotlightRect(null)
      }
    }
    const timer = setTimeout(findTarget, 150)
    return () => clearTimeout(timer)
  }, [step, current.target])

  const handleNext = () => {
    if (step < tourSteps.length - 1) {
      const next = tourSteps[step + 1]
      if (next.path && next.path !== tourSteps[step].path) {
        navigate(next.path)
      }
      setStep(step + 1)
    } else {
      localStorage.setItem('code4u_tour_completed', 'true')
      onComplete()
    }
  }

  const handleSkip = () => {
    localStorage.setItem('code4u_tour_completed', 'true')
    onComplete()
  }

  const pad = 8
  const sr = spotlightRect

  const cardTop = sr
    ? (sr.bottom + pad + 16 + 220 > window.innerHeight
        ? Math.max(8, sr.top - 220 - 16)
        : sr.bottom + 16)
    : undefined

  const cardLeft = sr
    ? Math.min(Math.max(16, sr.left), window.innerWidth - 400 - 16)
    : undefined

  return (
    <div className="fixed inset-0 z-[9999]">
      {/* Dimmed overlay with spotlight cutout */}
      <svg className="absolute inset-0 w-full h-full pointer-events-auto" onClick={handleSkip}>
        <defs>
          <mask id="tour-mask">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {sr && (
              <rect
                x={sr.left - pad} y={sr.top - pad}
                width={sr.width + pad * 2} height={sr.height + pad * 2}
                rx="12" fill="black"
              />
            )}
          </mask>
        </defs>
        <rect x="0" y="0" width="100%" height="100%" fill={darkMode ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.35)'} mask="url(#tour-mask)" />
      </svg>

      {/* Spotlight glow border around target */}
      {sr && (
        <div
          className="absolute pointer-events-none rounded-xl border-2 border-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.4)]"
          style={{
            left: sr.left - pad,
            top: sr.top - pad,
            width: sr.width + pad * 2,
            height: sr.height + pad * 2,
            transition: 'all 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      )}

      {/* Tour card — positioned near the highlighted element */}
      <div
        className={`absolute z-10 w-[380px] rounded-2xl shadow-2xl border overflow-hidden pointer-events-auto ${
          darkMode ? 'bg-[#0d1117] border-white/15' : 'bg-white border-slate-200'
        }`}
        style={sr ? {
          top: cardTop,
          left: cardLeft,
          transition: 'all 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
        } : {
          bottom: 32,
          left: '50%',
          transform: 'translateX(-50%)',
          transition: 'all 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        <div className="h-1 w-full" style={{ background: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }}>
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
            style={{ width: `${((step + 1) / tourSteps.length) * 100}%` }}
          />
        </div>

        <div className="px-5 pt-4 pb-2">
          <div className="flex items-center justify-between mb-1.5">
            <span className={`text-[10px] font-mono uppercase tracking-widest ${darkMode ? 'text-emerald-400/60' : 'text-emerald-600/60'}`}>
              Step {step + 1} of {tourSteps.length}
            </span>
            <div className="flex gap-0.5">
              {tourSteps.map((_, i) => (
                <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors ${i <= step ? 'bg-emerald-500' : (darkMode ? 'bg-white/10' : 'bg-slate-200')}`} />
              ))}
            </div>
          </div>
          <h2 className="text-sm font-bold mb-1">{current.title}</h2>
          <p className={`text-xs leading-relaxed ${darkMode ? 'text-white/60' : 'text-slate-600'}`}>
            {current.description}
          </p>
        </div>

        <div className={`flex items-center justify-between px-5 py-2.5 border-t ${
          darkMode ? 'border-white/10' : 'border-slate-100'
        }`}>
          <button
            onClick={handleSkip}
            className={`text-[11px] font-medium ${darkMode ? 'text-white/30 hover:text-white/60' : 'text-slate-400 hover:text-slate-600'}`}
          >
            Skip Tour
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => { const prev = tourSteps[step - 1]; if (prev.path !== current.path) navigate(prev.path); setStep(step - 1) }}
                className={`px-3 py-1.5 rounded-lg text-[11px] font-medium ${darkMode ? 'text-white/50 hover:bg-white/5' : 'text-slate-500 hover:bg-slate-100'}`}
              >
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              className="px-4 py-1.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-[11px] hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
            >
              {current.action}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { darkMode, themeMode, setThemeMode } = useDarkMode()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [showNotifications, setShowNotifications] = useState(false)
  const [showProfileMenu, setShowProfileMenu] = useState(false)
  const [showThemeMenu, setShowThemeMenu] = useState(false)
  const [notifications, setNotifications] = useState(mockNotifications)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [showTour, setShowTour] = useState(() => !localStorage.getItem('code4u_tour_completed'))

  const unreadCount = notifications.filter(n => !n.read).length

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const markAllRead = () => {
    setNotifications(notifications.map(n => ({ ...n, read: true })))
  }

  const clearNotification = (id: string) => {
    setNotifications(notifications.filter(n => n.id !== id))
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle size={16} className="text-emerald-500" />
      case 'warning': return <AlertTriangle size={16} className="text-amber-500" />
      default: return <Info size={16} className="text-blue-500" />
    }
  }
  
  const navItems = [
    { path: '/', label: 'Dashboard' },
    { path: '/projects', label: 'Projects' },
    { path: '/agent', label: 'AI Agent' },
    { path: '/guardian', label: 'Guardian' },
    { path: '/org-dashboard', label: 'Org Security' },
    { path: '/security', label: 'Security' },
    { path: '/integrations', label: 'Integrations' },
    { path: '/docs', label: 'Docs' },
  ]

  return (
    <div className={`min-h-screen transition-colors duration-300 ${darkMode ? '' : 'light'} ${
      darkMode 
        ? 'bg-gradient-to-br from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] text-white' 
        : 'bg-gradient-to-br from-slate-50 via-white to-slate-100 text-slate-900'
    }`}>
      {/* Header */}
      <header className={`border-b sticky top-0 z-50 transition-all duration-300 ${
        darkMode 
          ? 'border-white/[0.06] bg-[#0a0a0f]/70 backdrop-blur-2xl backdrop-saturate-150' 
          : 'border-slate-200/80 bg-white/70 backdrop-blur-2xl backdrop-saturate-150'
      }`}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-3" data-tour="logo">
              <img src="/logo.png" alt="code4u.ai" className="w-8 h-8 rounded-lg" />
              <span className="font-bold text-lg">code4u.ai</span>
            </Link>
            <nav className="flex items-center gap-1" data-tour="nav">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    location.pathname === item.path
                      ? darkMode ? 'bg-white/10 text-white' : 'bg-emerald-100 text-emerald-700'
                      : darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            {/* Search / Command Palette Trigger */}
            <button
              data-tour="search"
              onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
              className={`flex items-center gap-2 w-64 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                darkMode
                  ? 'bg-white/5 border border-white/10 text-white/40 hover:border-white/20 hover:bg-white/[0.07]'
                  : 'bg-slate-100 border border-slate-200 text-slate-400 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <Search className="w-4 h-4 shrink-0" />
              <span className="flex-1">Search...</span>
              <kbd className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                darkMode ? 'border-white/10 text-white/20' : 'border-slate-200 text-slate-300'
              }`}>⌘K</kbd>
            </button>
            
            {/* Theme Toggle */}
            <div className="relative" data-tour="theme">
              <button
                onClick={() => { setShowThemeMenu(!showThemeMenu); setShowNotifications(false); setShowProfileMenu(false) }}
                className={`p-2 rounded-lg transition-colors ${
                  darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
                title="Theme"
              >
                {themeMode === 'dark' ? <Moon className="w-5 h-5" /> : themeMode === 'light' ? <Sun className="w-5 h-5" /> : <Monitor className="w-5 h-5" />}
              </button>
              {showThemeMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowThemeMenu(false)} />
                  <div className={`absolute right-0 top-10 z-50 w-40 rounded-xl shadow-xl border overflow-hidden ${
                    darkMode ? 'bg-[#0d1117] border-white/10' : 'bg-white border-slate-200'
                  }`}>
                    {([
                      { mode: 'dark' as ThemeMode, icon: Moon, label: 'Dark' },
                      { mode: 'light' as ThemeMode, icon: Sun, label: 'Light' },
                      { mode: 'system' as ThemeMode, icon: Monitor, label: 'System' },
                    ]).map(({ mode, icon: Icon, label }) => (
                      <button
                        key={mode}
                        onClick={() => { setThemeMode(mode); setShowThemeMenu(false) }}
                        className={`flex items-center gap-3 w-full px-4 py-2.5 text-sm transition-colors ${
                          themeMode === mode
                            ? darkMode ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-600'
                            : darkMode ? 'text-white/70 hover:bg-white/5' : 'text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {label}
                        {themeMode === mode && <CheckCircle className="w-3 h-3 ml-auto" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Refresh Button */}
            <button 
              onClick={handleRefresh}
              className={`p-2 rounded-lg transition-colors ${
                darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>

            {/* Notifications */}
            <button 
              onClick={() => setShowNotifications(!showNotifications)}
              className={`p-2 rounded-lg transition-colors relative ${
                darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
              title="Notifications"
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-emerald-500 rounded-full"></span>
              )}
            </button>

            <Link 
              to="/settings" 
              className={`p-2 rounded-lg transition-colors ${
                darkMode ? 'text-white/60 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Settings className="w-5 h-5" />
            </Link>
            <button 
              data-tour="profile"
              onClick={() => { setShowProfileMenu(!showProfileMenu); setShowNotifications(false) }}
              className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-sm font-semibold text-white cursor-pointer hover:ring-2 hover:ring-purple-400 transition-all"
            >
              {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
            </button>
          </div>
        </div>

        {/* Profile Dropdown */}
        {showProfileMenu && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setShowProfileMenu(false)} />
            <div className={`absolute right-6 top-16 z-50 w-64 rounded-xl shadow-2xl border animate-scale-in ${
              darkMode ? 'glass border-white/10' : 'glass-light border-slate-200'
            }`}>
              <div className={`p-4 border-b ${darkMode ? 'border-white/10' : 'border-slate-100'}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-sm font-semibold text-white">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                  <div>
                    <p className="font-semibold text-sm">{user?.name || 'User'}</p>
                    <p className={`text-xs ${darkMode ? 'text-white/50' : 'text-slate-500'}`}>{user?.email || 'user@code4u.ai'}</p>
                  </div>
                </div>
              </div>
              <div className="py-1">
                {[
                  { icon: User, label: 'Profile', path: '/settings' },
                  { icon: Key, label: 'API Keys', path: '/settings' },
                  { icon: Shield, label: 'Security', path: '/security' },
                  { icon: CreditCard, label: 'Billing', path: '/settings' },
                ].map(({ icon: Icon, label, path }) => (
                  <Link
                    key={label}
                    to={path}
                    onClick={() => setShowProfileMenu(false)}
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                      darkMode ? 'text-white/70 hover:text-white hover:bg-white/5' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Link>
                ))}
              </div>
              <div className={`border-t py-1 ${darkMode ? 'border-white/10' : 'border-slate-100'}`}>
                <button
                  onClick={() => { setShowProfileMenu(false); logout(); navigate('/login') }}
                  className={`flex items-center gap-3 px-4 py-2.5 text-sm w-full transition-colors ${
                    darkMode ? 'text-red-400 hover:bg-white/5' : 'text-red-600 hover:bg-red-50'
                  }`}
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            </div>
          </>
        )}

        {/* Notifications Dropdown */}
        {showNotifications && (
          <>
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setShowNotifications(false)}
            />
            <div className={`absolute top-full right-6 mt-2 w-96 rounded-xl shadow-xl border z-50 overflow-hidden animate-slide-down ${
              darkMode ? 'glass border-white/10' : 'glass-light border-slate-200'
            }`}>
              <div className={`p-4 border-b flex items-center justify-between ${
                darkMode ? 'border-slate-700' : 'border-slate-200'
              }`}>
                <h3 className="font-semibold">Notifications</h3>
                {unreadCount > 0 && (
                  <button 
                    onClick={markAllRead}
                    className="text-sm text-emerald-500 hover:text-emerald-400"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-96 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className={`p-8 text-center ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                    No notifications
                  </div>
                ) : (
                  notifications.map(notification => (
                    <div 
                      key={notification.id}
                      className={`p-4 border-b transition-colors ${
                        darkMode 
                          ? `border-slate-700 hover:bg-slate-700/50 ${!notification.read ? 'bg-emerald-900/10' : ''}`
                          : `border-slate-100 hover:bg-slate-50 ${!notification.read ? 'bg-emerald-50' : ''}`
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5">
                          {getNotificationIcon(notification.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-sm truncate">{notification.title}</p>
                            <button 
                              onClick={() => clearNotification(notification.id)}
                              className={`${darkMode ? 'text-slate-400 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'}`}
                            >
                              <X size={14} />
                            </button>
                          </div>
                          <p className={`text-sm mt-0.5 ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>{notification.message}</p>
                          <p className={`text-xs mt-1 ${darkMode ? 'text-slate-500' : 'text-slate-400'}`}>{notification.time}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className={`p-3 border-t text-center ${darkMode ? 'border-slate-700' : 'border-slate-200'}`}>
                <button className="text-sm text-emerald-500 hover:text-emerald-400 font-medium">
                  View all notifications
                </button>
              </div>
            </div>
          </>
        )}
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8" data-tour="page-content">
        <motion.div
          key={location.pathname}
          initial="initial"
          animate="animate"
          exit="exit"
          variants={pageVariants}
        >
          {children}
        </motion.div>
      </main>

      {/* Command Palette */}
      <CommandPalette />

      {/* First-run onboarding tour */}
      {showTour && <OnboardingTour onComplete={() => setShowTour(false)} />}
    </div>
  )
}

function RedirectIfLoggedIn({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (isAuthenticated) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      {/* Auth pages — redirect to dashboard if already logged in */}
      <Route path="/login" element={<RedirectIfLoggedIn><LoginPage /></RedirectIfLoggedIn>} />
      <Route path="/signup" element={<RedirectIfLoggedIn><SignupPage /></RedirectIfLoggedIn>} />
      
      {/* Protected routes — require authentication */}
      <Route path="/ide" element={<RequireAuth><IDE /></RequireAuth>} />
      <Route path="/" element={<RequireAuth><Layout><DashboardPage /></Layout></RequireAuth>} />
      <Route path="/projects" element={<RequireAuth><Layout><ProjectsPage /></Layout></RequireAuth>} />
      <Route path="/agent" element={<RequireAuth><Layout><AgentPage /></Layout></RequireAuth>} />
      <Route path="/docs" element={<RequireAuth><Layout><DocsPage /></Layout></RequireAuth>} />
      <Route path="/connect-repo" element={<RequireAuth><Layout><ConnectRepoPage /></Layout></RequireAuth>} />
      <Route path="/refactor" element={<RequireAuth><Layout><RefactorPage /></Layout></RequireAuth>} />
      <Route path="/tutorials" element={<RequireAuth><Layout><TutorialsPage /></Layout></RequireAuth>} />
      <Route path="/new-project" element={<RequireAuth><Layout><NewProjectPage /></Layout></RequireAuth>} />
      <Route path="/extensions" element={<RequireAuth><Layout><ExtensionsPage /></Layout></RequireAuth>} />
      <Route path="/integrations" element={<RequireAuth><Layout><IntegrationsPage /></Layout></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><Layout><SettingsPage /></Layout></RequireAuth>} />
      <Route path="/security" element={<RequireAuth><Layout><SecurityPage /></Layout></RequireAuth>} />
      <Route path="/guardian" element={<RequireAuth><Layout><GuardianPage /></Layout></RequireAuth>} />
      <Route path="/org-dashboard" element={<RequireAuth><Layout><OrgDashboard /></Layout></RequireAuth>} />
      <Route path="/team" element={<RequireAuth><Layout><TeamPage /></Layout></RequireAuth>} />
    </Routes>
  )
}

function SettingsPage() {
  const { darkMode, themeMode, setThemeMode } = useDarkMode()
  const [activeTab, setActiveTab] = useState('profile')
  const [saved, setSaved] = useState(false)
  const [profile, setProfile] = useState({ name: 'User', email: 'user@code4u.ai', company: '', role: 'Developer' })
  const [notifications, setNotifications] = useState({ email: true, push: true, weekly: false, marketing: false })
  const [apiKeys, setApiKeys] = useState([
    { id: 1, name: 'Development', key: 'c4u_dev_••••••••abcd', created: '2026-01-15', lastUsed: '2026-01-31' },
  ])
  const [showNewKey, setShowNewKey] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [security, setSecurity] = useState({ twoFactor: false, sessionTimeout: '30' })
  const [airgap, setAirgap] = useState({ enabled: false, ollamaUrl: 'http://localhost:11434', provider: 'ollama' })

  const card = `rounded-xl p-6 ${darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'}`
  const input = `w-full px-4 py-2.5 rounded-lg border focus:outline-none focus:ring-2 focus:ring-emerald-500/30 ${darkMode ? 'bg-black/40 border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900'}`
  const label = `block text-sm font-medium mb-1.5 ${darkMode ? 'text-white/70' : 'text-slate-600'}`
  const sub = darkMode ? 'text-white/50' : 'text-slate-500'

  const handleSave = () => { setSaved(true); setTimeout(() => setSaved(false), 2000) }

  const [doctor, setDoctor] = useState<any>(null)
  const [doctorLoading, setDoctorLoading] = useState(false)

  const runDoctor = async () => {
    setDoctorLoading(true)
    try {
      const r = await fetch('/api/v1/health/doctor')
      if (r.ok) setDoctor(await r.json())
    } catch {}
    setDoctorLoading(false)
  }

  const tabs = [
    { id: 'profile', label: 'Profile' },
    { id: 'notifications', label: 'Notifications' },
    { id: 'apikeys', label: 'API Keys' },
    { id: 'security', label: 'Security' },
    { id: 'llm', label: 'LLM & Models' },
    { id: 'system', label: 'System Status' },
    { id: 'appearance', label: 'Appearance' },
  ]

  const generateKey = () => {
    const key = 'c4u_' + newKeyName.toLowerCase().replace(/\s+/g, '_') + '_' + Math.random().toString(36).slice(2, 14)
    setApiKeys([...apiKeys, { id: Date.now(), name: newKeyName || 'Untitled', key, created: new Date().toISOString().split('T')[0], lastUsed: 'Never' }])
    setNewKeyName('')
    setShowNewKey(false)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className={`mt-1 ${sub}`}>Manage your account and preferences</p>
      </div>

      {/* Tabs */}
      <div className={`flex gap-1 p-1 rounded-lg ${darkMode ? 'bg-white/5' : 'bg-slate-100'}`}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === t.id ? (darkMode ? 'bg-white/10 text-white' : 'bg-white text-slate-900 shadow-sm') : (darkMode ? 'text-white/50 hover:text-white' : 'text-slate-500 hover:text-slate-700')}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Profile */}
      {activeTab === 'profile' && (
        <div className={card}>
          <h2 className="font-semibold text-lg mb-4">Profile Information</h2>
          <div className="space-y-4">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-2xl font-bold text-white">{profile.name[0]}</div>
              <div>
                <p className="font-semibold">{profile.name}</p>
                <p className={`text-sm ${sub}`}>{profile.email}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className={label}>Full Name</label><input className={input} value={profile.name} onChange={e => setProfile({...profile, name: e.target.value})} /></div>
              <div><label className={label}>Email</label><input className={input} type="email" value={profile.email} onChange={e => setProfile({...profile, email: e.target.value})} /></div>
              <div><label className={label}>Company</label><input className={input} placeholder="Your company" value={profile.company} onChange={e => setProfile({...profile, company: e.target.value})} /></div>
              <div><label className={label}>Role</label>
                <select className={input} value={profile.role} onChange={e => setProfile({...profile, role: e.target.value})}>
                  <option>Developer</option><option>Tech Lead</option><option>Engineering Manager</option><option>CTO</option><option>Other</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button onClick={handleSave} className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all">
                {saved ? '✓ Saved' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {activeTab === 'notifications' && (
        <div className={card}>
          <h2 className="font-semibold text-lg mb-4">Notification Preferences</h2>
          <div className="space-y-4">
            {([
              { key: 'email' as const, title: 'Email Notifications', desc: 'Receive refactor results and alerts via email' },
              { key: 'push' as const, title: 'Push Notifications', desc: 'Browser push notifications for real-time updates' },
              { key: 'weekly' as const, title: 'Weekly Digest', desc: 'Weekly summary of refactoring activity and ROI' },
              { key: 'marketing' as const, title: 'Product Updates', desc: 'New features, tips, and platform updates' },
            ]).map(({ key, title, desc }) => (
              <div key={key} className={`flex items-center justify-between p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
                <div><p className="font-medium text-sm">{title}</p><p className={`text-xs mt-0.5 ${sub}`}>{desc}</p></div>
                <button onClick={() => setNotifications({...notifications, [key]: !notifications[key]})} className={`w-11 h-6 rounded-full transition-colors relative ${notifications[key] ? 'bg-emerald-500' : (darkMode ? 'bg-white/20' : 'bg-slate-300')}`}>
                  <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow ${notifications[key] ? 'translate-x-5.5 left-[1px]' : 'left-[2px]'}`} style={{ transform: notifications[key] ? 'translateX(21px)' : 'translateX(0)' }} />
                </button>
              </div>
            ))}
            <div className="flex justify-end pt-2">
              <button onClick={handleSave} className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all">
                {saved ? '✓ Saved' : 'Save Preferences'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Keys */}
      {activeTab === 'apikeys' && (
        <div className={card}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg">API Keys</h2>
            <button onClick={() => setShowNewKey(true)} className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-medium text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all">
              + New Key
            </button>
          </div>
          {showNewKey && (
            <div className={`p-4 rounded-lg mb-4 ${darkMode ? 'bg-black/30 border border-white/10' : 'bg-slate-50 border border-slate-200'}`}>
              <label className={label}>Key Name</label>
              <div className="flex gap-2">
                <input className={input} placeholder="e.g. Production, CI/CD" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} />
                <button onClick={generateKey} className="px-4 py-2 bg-emerald-500 text-white rounded-lg text-sm font-medium whitespace-nowrap">Generate</button>
                <button onClick={() => setShowNewKey(false)} className={`px-4 py-2 rounded-lg text-sm ${darkMode ? 'bg-white/10 text-white/70' : 'bg-slate-200 text-slate-600'}`}>Cancel</button>
              </div>
            </div>
          )}
          <div className="space-y-3">
            {apiKeys.map(k => (
              <div key={k.id} className={`flex items-center justify-between p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
                <div>
                  <p className="font-medium text-sm">{k.name}</p>
                  <p className={`text-xs font-mono mt-1 ${sub}`}>{k.key}</p>
                  <p className={`text-xs mt-1 ${sub}`}>Created {k.created} · Last used {k.lastUsed}</p>
                </div>
                <button onClick={() => setApiKeys(apiKeys.filter(a => a.id !== k.id))} className="text-red-400 hover:text-red-300 text-sm">Revoke</button>
              </div>
            ))}
            {apiKeys.length === 0 && <p className={`text-sm text-center py-8 ${sub}`}>No API keys yet. Create one to get started.</p>}
          </div>
        </div>
      )}

      {/* Security */}
      {activeTab === 'security' && (
        <div className={card}>
          <h2 className="font-semibold text-lg mb-4">Security</h2>
          <div className="space-y-4">
            <div className={`flex items-center justify-between p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <div><p className="font-medium text-sm">Two-Factor Authentication</p><p className={`text-xs mt-0.5 ${sub}`}>Add an extra layer of security to your account</p></div>
              <button onClick={() => setSecurity({...security, twoFactor: !security.twoFactor})} className={`w-11 h-6 rounded-full transition-colors relative ${security.twoFactor ? 'bg-emerald-500' : (darkMode ? 'bg-white/20' : 'bg-slate-300')}`}>
                <div className="w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow" style={{ transform: security.twoFactor ? 'translateX(21px)' : 'translateX(0)', left: security.twoFactor ? '1px' : '2px' }} />
              </button>
            </div>
            <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <label className={label}>Session Timeout (minutes)</label>
              <select className={input} value={security.sessionTimeout} onChange={e => setSecurity({...security, sessionTimeout: e.target.value})}>
                <option value="15">15 minutes</option><option value="30">30 minutes</option><option value="60">1 hour</option><option value="480">8 hours</option><option value="1440">24 hours</option>
              </select>
            </div>
            <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <p className="font-medium text-sm">Change Password</p>
              <p className={`text-xs mt-0.5 mb-3 ${sub}`}>Update your password regularly for better security</p>
              <div className="space-y-2">
                <input className={input} type="password" placeholder="Current password" />
                <input className={input} type="password" placeholder="New password" />
                <input className={input} type="password" placeholder="Confirm new password" />
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button onClick={handleSave} className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all">
                {saved ? '✓ Saved' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LLM & Models (Air-Gapped Mode) */}
      {activeTab === 'llm' && (
        <div className={card}>
          <h2 className="font-semibold text-lg mb-4">LLM Provider & Air-Gapped Mode</h2>
          <div className="space-y-4">
            <div className={`flex items-center justify-between p-4 rounded-lg border ${airgap.enabled ? (darkMode ? 'bg-amber-900/20 border-amber-500/30' : 'bg-amber-50 border-amber-200') : (darkMode ? 'bg-black/30 border-white/10' : 'bg-slate-50 border-slate-200')}`}>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium text-sm">Air-Gapped Mode</p>
                  {airgap.enabled && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-bold uppercase tracking-wider">Active</span>}
                </div>
                <p className={`text-xs mt-0.5 ${sub}`}>Block all external API calls. Only local models (Ollama/vLLM) will be used. Zero tokens sent to cloud providers.</p>
              </div>
              <button onClick={() => setAirgap({...airgap, enabled: !airgap.enabled})} className={`w-11 h-6 rounded-full transition-colors relative ${airgap.enabled ? 'bg-amber-500' : (darkMode ? 'bg-white/20' : 'bg-slate-300')}`}>
                <div className="w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow" style={{ transform: airgap.enabled ? 'translateX(21px)' : 'translateX(0)', left: airgap.enabled ? '1px' : '2px' }} />
              </button>
            </div>

            <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <label className={label}>Default LLM Provider</label>
              <select className={input} value={airgap.provider} onChange={e => setAirgap({...airgap, provider: e.target.value})}>
                <option value="ollama">Ollama (Local)</option>
                <option value="vllm">vLLM (Self-hosted)</option>
                {!airgap.enabled && <option value="openai">OpenAI</option>}
                {!airgap.enabled && <option value="anthropic">Anthropic</option>}
                {!airgap.enabled && <option value="google">Google</option>}
                {!airgap.enabled && <option value="groq">Groq</option>}
              </select>
            </div>

            <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <label className={label}>Ollama Server URL</label>
              <input className={input} value={airgap.ollamaUrl} onChange={e => setAirgap({...airgap, ollamaUrl: e.target.value})} placeholder="http://localhost:11434" />
              <p className={`text-xs mt-1.5 ${sub}`}>OpenAI-compatible endpoint at /v1/chat/completions</p>
            </div>

            <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
              <p className="font-medium text-sm mb-2">Model Routing Table</p>
              <p className={`text-xs mb-3 ${sub}`}>Tasks are routed to different models based on complexity. Low-complexity tasks use cheap/local models; high-complexity tasks use premium models.</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { agent: 'Chief Architect', local: 'deepseek-coder-v2', cloud: 'gpt-4o' },
                  { agent: 'Refactor', local: 'deepseek-coder-v2', cloud: 'claude-sonnet-4' },
                  { agent: 'Heal', local: 'qwen2.5-coder:32b', cloud: 'claude-sonnet-4' },
                  { agent: 'Profiler', local: 'llama3.1', cloud: 'gpt-4o-mini' },
                  { agent: 'Deploy', local: 'llama3.1', cloud: 'gpt-4o-mini' },
                  { agent: 'Chat', local: 'llama3.1', cloud: 'gpt-4o-mini' },
                ].map(r => (
                  <div key={r.agent} className={`flex items-center justify-between p-2 rounded ${darkMode ? 'bg-white/5' : 'bg-white'}`}>
                    <span className="font-medium">{r.agent}</span>
                    <span className={`font-mono ${sub}`}>{airgap.enabled ? r.local : r.cloud}</span>
                  </div>
                ))}
              </div>
            </div>

            {airgap.enabled && (
              <div className={`p-4 rounded-lg border ${darkMode ? 'bg-emerald-900/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-200'}`}>
                <p className="font-medium text-sm text-emerald-500">Token costs: $0.00</p>
                <p className={`text-xs mt-1 ${sub}`}>All inference runs locally. No data leaves your network.</p>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button onClick={handleSave} className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-semibold text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all">
                {saved ? '✓ Saved' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* System Status (Doctor) */}
      {activeTab === 'system' && (
        <div className={card}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg">System Diagnostics</h2>
            <button onClick={runDoctor} disabled={doctorLoading} className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-medium text-white text-sm hover:shadow-lg hover:shadow-emerald-500/25 transition-all disabled:opacity-50">
              {doctorLoading ? 'Running...' : 'Run Diagnostics'}
            </button>
          </div>

          {!doctor && !doctorLoading && (
            <p className={`text-sm ${sub}`}>Click "Run Diagnostics" to check all system dependencies.</p>
          )}

          {doctor && (
            <div className="space-y-4">
              <div className={`flex items-center justify-between p-4 rounded-lg border ${
                doctor.overall === 'healthy' ? (darkMode ? 'bg-emerald-900/20 border-emerald-500/30' : 'bg-emerald-50 border-emerald-200')
                : doctor.overall === 'degraded' ? (darkMode ? 'bg-amber-900/20 border-amber-500/30' : 'bg-amber-50 border-amber-200')
                : (darkMode ? 'bg-red-900/20 border-red-500/30' : 'bg-red-50 border-red-200')
              }`}>
                <div>
                  <p className="font-semibold text-lg">{doctor.readinessScore}% Ready</p>
                  <p className={`text-xs ${sub}`}>Overall: {doctor.overall} | Environment: {doctor.environment}</p>
                </div>
                <div className={`text-3xl font-bold ${
                  doctor.overall === 'healthy' ? 'text-emerald-500' : doctor.overall === 'degraded' ? 'text-amber-500' : 'text-red-500'
                }`}>
                  {doctor.overall === 'healthy' ? 'OK' : doctor.overall === 'degraded' ? '!!' : 'XX'}
                </div>
              </div>

              <div className="space-y-2">
                {doctor.probes?.map((p: any) => (
                  <div key={p.name} className={`flex items-center justify-between p-3 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-slate-50'}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${
                        p.status === 'healthy' ? 'bg-emerald-500'
                        : p.status === 'degraded' ? 'bg-amber-500'
                        : p.status === 'active' ? 'bg-blue-500'
                        : p.status === 'inactive' ? 'bg-slate-400'
                        : 'bg-red-500'
                      }`} />
                      <div>
                        <p className="font-medium text-sm">{p.name}</p>
                        {p.error && <p className="text-xs text-red-400 mt-0.5">{p.error}</p>}
                        {p.note && <p className={`text-xs mt-0.5 ${sub}`}>{p.note}</p>}
                        {p.backend && <p className={`text-xs mt-0.5 ${sub}`}>Backend: {p.backend}</p>}
                        {p.path && <p className={`text-xs mt-0.5 font-mono ${sub}`}>{p.path}</p>}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        p.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-400'
                        : p.status === 'degraded' ? 'bg-amber-500/20 text-amber-400'
                        : p.status === 'active' ? 'bg-blue-500/20 text-blue-400'
                        : p.status === 'inactive' ? (darkMode ? 'bg-white/10 text-white/40' : 'bg-slate-200 text-slate-500')
                        : 'bg-red-500/20 text-red-400'
                      }`}>{p.status}</span>
                      {p.latencyMs != null && <p className={`text-[10px] mt-1 ${sub}`}>{p.latencyMs}ms</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Appearance */}
      {activeTab === 'appearance' && (
        <div className={card}>
          <h2 className="font-semibold text-lg mb-4">Appearance</h2>
          <div className="space-y-4">
            <div>
              <p className="font-medium text-sm mb-3">Theme</p>
              <div className="grid grid-cols-3 gap-3">
                {([
                  { mode: 'dark' as const, label: 'Dark', desc: 'Easy on the eyes', preview: 'bg-[#0d1117]' },
                  { mode: 'light' as const, label: 'Light', desc: 'Clean and bright', preview: 'bg-slate-100' },
                  { mode: 'system' as const, label: 'System', desc: 'Match your OS', preview: 'bg-gradient-to-r from-[#0d1117] to-slate-100' },
                ]).map(({ mode, label, desc, preview }) => (
                  <button
                    key={mode}
                    onClick={() => setThemeMode(mode)}
                    className={`p-4 rounded-xl border transition-all text-left ${
                      themeMode === mode
                        ? 'border-emerald-500 ring-1 ring-emerald-500/20 bg-emerald-500/5'
                        : darkMode ? 'border-white/10 hover:border-white/20' : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className={`w-full h-12 rounded-lg mb-3 ${preview}`} />
                    <p className="font-medium text-sm">{label}</p>
                    <p className={`text-xs mt-0.5 ${sub}`}>{desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Danger Zone */}
      {activeTab === 'profile' && (
        <div className={`rounded-xl p-6 border ${darkMode ? 'border-red-500/30 bg-red-500/5' : 'border-red-200 bg-red-50'}`}>
          <h2 className="font-semibold text-red-500 mb-2">Danger Zone</h2>
          <p className={`text-sm mb-4 ${sub}`}>Permanently delete your account and all associated data.</p>
          <button className="px-4 py-2 border border-red-500/50 text-red-500 rounded-lg text-sm font-medium hover:bg-red-500/10 transition-colors">
            Delete Account
          </button>
        </div>
      )}
    </div>
  )
}

function TeamPage() {
  const { darkMode } = useDarkMode()
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Team</h1>
      <p className={darkMode ? 'text-white/50' : 'text-slate-500'}>Manage team members and permissions</p>
      <div className={`rounded-xl p-6 ${
        darkMode ? 'bg-white/5 border border-white/10' : 'bg-white border border-slate-200 shadow-sm'
      }`}>
        <h2 className="font-semibold mb-4">Team Members</h2>
        <div className="space-y-3">
          {['You (Owner)', 'Team Member 1', 'Team Member 2'].map((member, i) => (
            <div key={i} className={`flex items-center justify-between p-3 rounded-lg ${
              darkMode ? 'bg-black/30' : 'bg-slate-50'
            }`}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-sm text-white">
                  {member[0]}
                </div>
                <span>{member}</span>
              </div>
              <span className={`text-sm ${darkMode ? 'text-white/50' : 'text-slate-500'}`}>{i === 0 ? 'Owner' : 'Member'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    return (localStorage.getItem('code4u_theme') as ThemeMode) || 'dark'
  })

  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('code4u_theme') as ThemeMode | null
    if (saved === 'light') return false
    if (saved === 'dark') return true
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    localStorage.setItem('code4u_theme', themeMode)
    if (themeMode === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      setDarkMode(mq.matches)
      const handler = (e: MediaQueryListEvent) => setDarkMode(e.matches)
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    } else {
      setDarkMode(themeMode === 'dark')
    }
  }, [themeMode])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    document.documentElement.classList.toggle('light', !darkMode)
  }, [darkMode])

  return (
    <DarkModeContext.Provider value={{ darkMode, setDarkMode, themeMode, setThemeMode }}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </DarkModeContext.Provider>
  )
}
