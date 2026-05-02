import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { 
  Mail, 
  Lock, 
  Eye, 
  EyeOff,
  ArrowRight,
  ArrowLeft,
  Github,
  Chrome,
  Loader2,
} from 'lucide-react'
import { useAuth } from '../AuthContext'

function readOAuthSigningInFromHash(): boolean {
  if (typeof window === 'undefined') return false
  const h = window.location.hash
  return h.startsWith('#c4u_token=') && h.length > '#c4u_token='.length
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, oauthCompleteFromToken } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [oauthSigningIn, setOauthSigningIn] = useState(readOAuthSigningInFromHash)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauthErr = params.get('oauth_error')
    if (oauthErr) {
      setOauthSigningIn(false)
      setError(decodeURIComponent(oauthErr))
      window.history.replaceState(null, '', '/login')
      return
    }
    const hash = window.location.hash
    if (!hash.startsWith('#c4u_token=')) return
    const jwt = hash.slice('#c4u_token='.length)
    if (!jwt) {
      setOauthSigningIn(false)
      return
    }
    setOauthSigningIn(true)
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
    void (async () => {
      const result = await oauthCompleteFromToken(jwt)
      if (result.ok) {
        setOauthSigningIn(false)
        navigate('/')
      } else {
        setOauthSigningIn(false)
        setError(result.error || 'Sign-in failed')
      }
    })()
  }, [navigate, oauthCompleteFromToken])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    const result = await login(email, password)
    setIsLoading(false)
    if (result.ok) {
      navigate('/')
    } else {
      setError(result.error || 'Login failed')
    }
  }

  const handleSocialLogin = (provider: string) => {
    if (provider === 'google') {
      window.location.href = '/api/v1/auth/google/login'
      return
    }
    if (provider === 'github') {
      window.location.href = '/api/v1/auth/github/login?flow=sso'
      return
    }
    setError('This provider is not wired yet — use email/password, Google, or GitHub')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] flex items-center justify-center p-4 relative">
      {oauthSigningIn && (
        <div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-4 bg-[#0a0a0f]/95 backdrop-blur-md px-6"
          aria-live="polite"
          aria-busy="true"
        >
          <Loader2 className="h-10 w-10 animate-spin text-emerald-400" aria-hidden />
          <p className="text-lg font-medium text-white">Signing you in…</p>
          <p className="text-sm text-white/50 text-center max-w-sm">
            Completing sign-in. This only takes a moment.
          </p>
        </div>
      )}
      {/* Back to Home */}
      <a
        href="http://localhost:3000"
        className="fixed top-6 left-6 flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors z-50"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Home
      </a>

      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <a href="http://localhost:3000" className="inline-flex items-center gap-3 mb-4 hover:opacity-80 transition-opacity">
            <img src="/logo.png" alt="code4u.ai" className="w-12 h-12 rounded-xl" />
            <span className="text-2xl font-bold text-white">code4u.ai</span>
          </a>
          <p className="text-white/50">Sign in to your account</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}
          {/* Social Login */}
          <div className="space-y-3 mb-6">
            <button
              onClick={() => handleSocialLogin('github')}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 border border-white/10 rounded-xl font-medium hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <Github className="w-5 h-5" />
              Continue with GitHub
            </button>
            <button
              onClick={() => handleSocialLogin('google')}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 border border-white/10 rounded-xl font-medium hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <Chrome className="w-5 h-5" />
              Continue with Google
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-sm text-white/40">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Email Login Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">Email</label>
              <div className="relative">
                <Mail className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full pl-11 pr-4 py-3 bg-black/40 border border-white/10 rounded-xl focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">Password</label>
              <div className="relative">
                <Lock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-11 pr-12 py-3 bg-black/40 border border-white/10 rounded-xl focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="w-4 h-4 rounded border-white/20 bg-black/40 text-emerald-500 focus:ring-emerald-500/20" />
                <span className="text-white/60">Remember me</span>
              </label>
              <button type="button" className="text-emerald-400 hover:text-emerald-300">
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl font-semibold hover:shadow-lg hover:shadow-emerald-500/25 transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  Sign In
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Sign Up Link */}
        <p className="text-center mt-6 text-white/50">
          Don't have an account?{' '}
          <button 
            onClick={() => navigate('/signup')}
            className="text-emerald-400 hover:text-emerald-300 font-medium"
          >
            Sign up for free
          </button>
        </p>

        {/* Footer */}
        <p className="text-center mt-8 text-xs text-white/30">
          By signing in, you agree to our{' '}
          <a href="#" className="text-white/50 hover:text-white">Terms of Service</a>
          {' '}and{' '}
          <a href="#" className="text-white/50 hover:text-white">Privacy Policy</a>
        </p>
      </div>
    </div>
  )
}

