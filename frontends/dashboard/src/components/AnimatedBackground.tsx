import { useEffect, useRef, useState } from 'react'

// Binary rain effect - Matrix-style falling binary
export function BinaryRain() {
  const columns = 30 // More columns for better coverage
  
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-10">
      {[...Array(columns)].map((_, i) => (
        <BinaryColumn key={i} index={i} />
      ))}
    </div>
  )
}

function BinaryColumn({ index }: { index: number }) {
  const [bits, setBits] = useState<string[]>([])
  const delay = index * 3 // Staggered start
  const duration = 45 + Math.random() * 30 // 45-75 seconds to fall (slow and gentle)
  const left = (index / 30) * 100 + Math.random() * 2 - 1 // Spread across 30 columns
  const opacity = 0.2 + (index % 5) * 0.06 // 20-50% opacity for better visibility

  useEffect(() => {
    const generateBits = () => {
      const newBits = []
      const length = 15 + Math.floor(Math.random() * 15)
      for (let i = 0; i < length; i++) {
        newBits.push(Math.random() > 0.5 ? '1' : '0')
      }
      setBits(newBits)
    }
    generateBits()
    const interval = setInterval(generateBits, duration * 1000)
    return () => clearInterval(interval)
  }, [duration])

  return (
    <div
      className="absolute top-0 text-sm font-mono animate-binary-fall-slow whitespace-pre leading-loose"
      style={{
        left: `${left}%`,
        animationDelay: `${delay}s`,
        animationDuration: `${duration}s`,
        opacity,
        textShadow: '0 0 8px currentColor',
      }}
    >
      {bits.map((bit, i) => (
        <div 
          key={i} 
          className={bit === '1' ? 'text-emerald-400' : 'text-cyan-500'}
        >
          {bit}
        </div>
      ))}
    </div>
  )
}

// Floating code snippets
export function FloatingCode() {
  const codeSnippets = [
    'const refactor = await kg.analyze()',
    'if (validated) apply(diff)',
    'state: VERIFIED → APPLIED',
    'import { execute } from "code4u"',
    'await graph.traverse(node)',
    'schema.validate(changes)',
    'rollback.enable(7_days)',
    '{ status: "success" }',
    'deterministic: true',
    'hallucinations: 0',
    'async function plan()',
    'export type Intent =',
    'class KnowledgeGraph',
    '@validate_schema',
    'def execute_refactor():',
    'contract.enforce()',
    'audit.log(change)',
    'tenant.isolate()',
  ]

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {codeSnippets.map((snippet, i) => (
        <FloatingSnippet key={i} text={snippet} index={i} />
      ))}
    </div>
  )
}

function FloatingSnippet({ text, index }: { text: string; index: number }) {
  const top = 5 + (index * 5) % 90
  const delay = index * 3
  const duration = 45 + Math.random() * 30 // Slower
  const opacity = 0.06 + Math.random() * 0.08 // More subtle: 6-14%

  return (
    <div
      className="absolute text-[10px] font-mono text-emerald-400/60 whitespace-nowrap animate-float-horizontal"
      style={{
        top: `${top}%`,
        animationDelay: `${delay}s`,
        animationDuration: `${duration}s`,
        opacity,
      }}
    >
      {text}
    </div>
  )
}

// Circuit lines
export function CircuitLines() {
  return (
    <svg className="absolute inset-0 w-full h-full opacity-[0.03] pointer-events-none">
      <defs>
        <linearGradient id="circuit-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0" />
          <stop offset="50%" stopColor="#10b981" stopOpacity="1" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      
      {/* Horizontal lines */}
      {[...Array(8)].map((_, i) => (
        <g key={`h-${i}`}>
          <line
            x1="0"
            y1={`${10 + i * 12}%`}
            x2="100%"
            y2={`${10 + i * 12}%`}
            stroke="url(#circuit-gradient)"
            strokeWidth="1"
            className="animate-circuit-h"
            style={{ animationDelay: `${i * 0.5}s` }}
          />
          {/* Nodes */}
          {[...Array(5)].map((_, j) => (
            <circle
              key={j}
              cx={`${20 + j * 15}%`}
              cy={`${10 + i * 12}%`}
              r="3"
              fill="#10b981"
              className="animate-pulse-node"
              style={{ animationDelay: `${(i + j) * 0.3}s` }}
            />
          ))}
        </g>
      ))}
      
      {/* Vertical lines */}
      {[...Array(6)].map((_, i) => (
        <line
          key={`v-${i}`}
          x1={`${15 + i * 15}%`}
          y1="0"
          x2={`${15 + i * 15}%`}
          y2="100%"
          stroke="url(#circuit-gradient)"
          strokeWidth="1"
          className="animate-circuit-v"
          style={{ animationDelay: `${i * 0.7}s` }}
        />
      ))}
    </svg>
  )
}

// Data packets flowing
export function DataFlow() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[...Array(12)].map((_, i) => (
        <DataPacket key={i} index={i} />
      ))}
    </div>
  )
}

function DataPacket({ index }: { index: number }) {
  const paths = [
    { start: { x: 0, y: 20 }, end: { x: 100, y: 40 } },
    { start: { x: 100, y: 30 }, end: { x: 0, y: 60 } },
    { start: { x: 0, y: 50 }, end: { x: 100, y: 80 } },
    { start: { x: 100, y: 70 }, end: { x: 0, y: 90 } },
  ]
  const path = paths[index % paths.length]
  const delay = index * 1.5
  const duration = 8 + Math.random() * 4
  const size = 2 + Math.random() * 2
  const colors = ['bg-emerald-400', 'bg-cyan-400', 'bg-violet-400', 'bg-blue-400']

  return (
    <div
      className={`absolute rounded-full ${colors[index % colors.length]} opacity-60 animate-data-flow blur-[1px]`}
      style={{
        width: size,
        height: size,
        left: `${path.start.x}%`,
        top: `${path.start.y}%`,
        '--end-x': `${path.end.x}vw`,
        '--end-y': `${path.end.y}vh`,
        animationDelay: `${delay}s`,
        animationDuration: `${duration}s`,
      } as React.CSSProperties}
    />
  )
}

// Hexagon grid
export function HexGrid() {
  return (
    <div className="absolute inset-0 overflow-hidden opacity-[0.02] pointer-events-none">
      <svg width="100%" height="100%" className="absolute inset-0">
        <defs>
          <pattern id="hexagons" width="56" height="100" patternUnits="userSpaceOnUse" patternTransform="scale(2)">
            <polygon
              points="24.8,22 37.6,29.6 37.6,44.8 24.8,52.4 12,44.8 12,29.6"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
            />
            <polygon
              points="24.8,67 37.6,74.6 37.6,89.8 24.8,97.4 12,89.8 12,74.6"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
            />
            <polygon
              points="52.8,0 65.6,7.6 65.6,22.8 52.8,30.4 40,22.8 40,7.6"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
            />
            <polygon
              points="52.8,45 65.6,52.6 65.6,67.8 52.8,75.4 40,67.8 40,52.6"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hexagons)" className="text-white" />
      </svg>
    </div>
  )
}

// Particle system
export function ParticleField() {
  const particles = 50

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[...Array(particles)].map((_, i) => (
        <Particle key={i} index={i} />
      ))}
    </div>
  )
}

function Particle({ index }: { index: number }) {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 1 + Math.random() * 2
  const duration = 10 + Math.random() * 20
  const delay = Math.random() * 10

  return (
    <div
      className="absolute rounded-full bg-white opacity-20 animate-particle"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
      }}
    />
  )
}

// Code execution visualization
export function CodeExecution() {
  const [lines, setLines] = useState<{ text: string; type: string }[]>([])

  const execLines = [
    { text: '▶ Intent received: refactor', type: 'info' },
    { text: '◉ Parsing AST...', type: 'process' },
    { text: '✓ 47 nodes analyzed', type: 'success' },
    { text: '◉ Building dependency graph...', type: 'process' },
    { text: '✓ 12 connections mapped', type: 'success' },
    { text: '◉ Validating schema...', type: 'process' },
    { text: '✓ No breaking changes', type: 'success' },
    { text: '◉ Generating diff...', type: 'process' },
    { text: '✓ 3 files modified', type: 'success' },
    { text: '▶ State: VERIFIED', type: 'info' },
    { text: '✓ Applied successfully', type: 'success' },
  ]

  useEffect(() => {
    let index = 0
    const interval = setInterval(() => {
      setLines(prev => {
        const newLines = [...prev, execLines[index % execLines.length]]
        if (newLines.length > 8) newLines.shift()
        return newLines
      })
      index++
    }, 1200)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="absolute bottom-24 left-8 font-mono text-xs pointer-events-none bg-black/30 backdrop-blur-sm rounded-lg p-4 border border-white/10">
      {lines.map((line, i) => (
        <div
          key={i}
          className={`animate-fade-in ${
            line.type === 'success' ? 'text-emerald-400' :
            line.type === 'process' ? 'text-cyan-400' :
            'text-white'
          }`}
          style={{
            textShadow: line.type === 'success' 
              ? '0 0 10px rgba(52, 211, 153, 0.8)' 
              : line.type === 'process' 
                ? '0 0 10px rgba(34, 211, 238, 0.8)' 
                : '0 0 10px rgba(255, 255, 255, 0.5)'
          }}
        >
          {line.text}
        </div>
      ))}
    </div>
  )
}

// State machine visualization
export function StateMachineViz() {
  const states = ['INIT', 'ANALYZED', 'PLANNED', 'VALIDATED', 'GENERATED', 'VERIFIED', 'APPLIED']
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex(i => (i + 1) % states.length)
    }, 1500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="absolute top-24 right-8 pointer-events-none bg-black/30 backdrop-blur-sm rounded-lg p-4 border border-white/10">
      <div className="text-[10px] text-white/50 mb-3 font-mono uppercase tracking-wider">State Machine</div>
      <div className="flex flex-col gap-2">
        {states.map((state, i) => (
          <div key={state} className="flex items-center gap-3">
            <div 
              className={`w-3 h-3 rounded-full transition-all duration-300 ${
                i === activeIndex ? 'bg-emerald-400 scale-125' :
                i < activeIndex ? 'bg-emerald-400/70' : 'bg-white/20'
              }`}
              style={{
                boxShadow: i === activeIndex ? '0 0 15px rgba(52, 211, 153, 1), 0 0 30px rgba(52, 211, 153, 0.5)' : 
                           i < activeIndex ? '0 0 8px rgba(52, 211, 153, 0.5)' : 'none'
              }}
            />
            <span 
              className={`text-xs font-mono font-semibold transition-all duration-300 ${
                i === activeIndex ? 'text-emerald-400' : i < activeIndex ? 'text-emerald-400/70' : 'text-white/40'
              }`}
              style={{
                textShadow: i === activeIndex ? '0 0 10px rgba(52, 211, 153, 0.8)' : 'none'
              }}
            >
              {state}
            </span>
            {i === activeIndex && (
              <span className="text-[10px] text-cyan-400 animate-pulse">●</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Main animated background component
export function AnimatedBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Base gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950" />
      
      {/* Ambient glows */}
      <div className="absolute -top-40 -right-40 w-[800px] h-[800px] bg-gradient-to-br from-violet-600/20 via-fuchsia-600/10 to-transparent rounded-full blur-3xl animate-pulse-slow" />
      <div className="absolute -bottom-40 -left-40 w-[600px] h-[600px] bg-gradient-to-tr from-cyan-600/20 via-emerald-600/10 to-transparent rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '2s' }} />
      <div className="absolute top-1/3 left-1/2 w-[500px] h-[500px] bg-gradient-to-r from-blue-600/10 to-purple-600/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '4s' }} />
      
      {/* Grid */}
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSA2MCAwIEwgMCAwIDAgNjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-60" />
      
      {/* Effects layers */}
      <FloatingCode />
      <HexGrid />
      <CircuitLines />
      <DataFlow />
      <ParticleField />
      <CodeExecution />
      <StateMachineViz />
      
      {/* Noise overlay */}
      <div className="absolute inset-0 opacity-[0.015]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
      }} />
      
      {/* Vignette */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/50 via-transparent to-black/50" />
      <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/50" />
    </div>
  )
}

export default AnimatedBackground

