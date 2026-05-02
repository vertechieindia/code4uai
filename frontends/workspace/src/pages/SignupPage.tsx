import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Mail, 
  Lock, 
  User,
  Eye, 
  EyeOff,
  ArrowRight,
  ArrowLeft,
  Github,
  Chrome,
  CheckCircle2
} from 'lucide-react'
import { useAuth } from '../AuthContext'

export default function SignupPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    const result = await register(email, password, name)
    setIsLoading(false)
    if (result.ok) {
      navigate('/')
    } else {
      setError(result.error || 'Registration failed')
    }
  }

  const handleSocialSignup = (provider: string) => {
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

  const passwordStrength = password.length >= 8 ? 'strong' : password.length >= 4 ? 'medium' : 'weak'

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] flex items-center justify-center p-4">
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
          <p className="text-white/50">Create your free account</p>
        </div>

        {/* Signup Card */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}
          {/* Social Signup */}
          <div className="space-y-3 mb-6">
            <button
              onClick={() => handleSocialSignup('github')}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 border border-white/10 rounded-xl font-medium hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <Github className="w-5 h-5" />
              Continue with GitHub
            </button>
            <button
              onClick={() => handleSocialSignup('google')}
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

          {/* Email Signup Form */}
          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">Full Name</label>
              <div className="relative">
                <User className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full pl-11 pr-4 py-3 bg-black/40 border border-white/10 rounded-xl focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20"
                  required
                />
              </div>
            </div>

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
              {password && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    <div className={`h-1 flex-1 rounded ${passwordStrength === 'weak' ? 'bg-red-500' : passwordStrength === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                    <div className={`h-1 flex-1 rounded ${passwordStrength === 'medium' || passwordStrength === 'strong' ? (passwordStrength === 'medium' ? 'bg-amber-500' : 'bg-emerald-500') : 'bg-white/10'}`} />
                    <div className={`h-1 flex-1 rounded ${passwordStrength === 'strong' ? 'bg-emerald-500' : 'bg-white/10'}`} />
                  </div>
                  <p className={`text-xs mt-1 ${passwordStrength === 'weak' ? 'text-red-400' : passwordStrength === 'medium' ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {passwordStrength === 'weak' ? 'Weak password' : passwordStrength === 'medium' ? 'Medium strength' : 'Strong password'}
                  </p>
                </div>
              )}
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
                  Create Account
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>

          {/* Benefits */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <p className="text-sm text-white/50 mb-3">What you'll get:</p>
            <ul className="space-y-2">
              {[
                'Full access to AI coding assistant',
                'Unlimited projects',
                'Free tier with generous limits',
              ].map((benefit, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-white/70">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  {benefit}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Login Link */}
        <p className="text-center mt-6 text-white/50">
          Already have an account?{' '}
          <button 
            onClick={() => navigate('/login')}
            className="text-emerald-400 hover:text-emerald-300 font-medium"
          >
            Sign in
          </button>
        </p>

        {/* Footer */}
        <p className="text-center mt-8 text-xs text-white/30">
          By signing up, you agree to our{' '}
          <a href="#" className="text-white/50 hover:text-white">Terms of Service</a>
          {' '}and{' '}
          <a href="#" className="text-white/50 hover:text-white">Privacy Policy</a>
        </p>
      </div>
    </div>
  )
}
