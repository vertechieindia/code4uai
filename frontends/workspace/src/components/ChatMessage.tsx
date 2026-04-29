import { useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import {
  Sparkles,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Brain,
  Lightbulb,
} from 'lucide-react'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  code?: string
  onCopy?: (text: string) => void
  onApply?: (code: string) => void
}

const THOUGHT_REGEX = /(?:<think>|<thought>|<reasoning>)([\s\S]*?)(?:<\/think>|<\/thought>|<\/reasoning>)/gi
const THOUGHT_PREFIX = /^(?:Thinking:|Reasoning:|My thought process:).+$/im

function extractThoughts(content: string): { thoughts: string[]; clean: string } {
  const thoughts: string[] = []
  let clean = content

  let match
  const regex = new RegExp(THOUGHT_REGEX)
  while ((match = regex.exec(content)) !== null) {
    thoughts.push(match[1].trim())
    clean = clean.replace(match[0], '')
  }

  const prefixMatch = THOUGHT_PREFIX.exec(clean)
  if (prefixMatch) {
    const idx = clean.indexOf(prefixMatch[0])
    const endIdx = clean.indexOf('\n\n', idx)
    if (endIdx > idx) {
      thoughts.push(clean.slice(idx, endIdx).trim())
      clean = clean.slice(0, idx) + clean.slice(endIdx)
    }
  }

  return { thoughts, clean: clean.trim() }
}

const ThoughtBubble = memo(({ thoughts }: { thoughts: string[] }) => {
  const [expanded, setExpanded] = useState(false)
  if (thoughts.length === 0) return null

  return (
    <div className="mb-2">
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex items-center gap-1.5 text-[11px] text-violet-400/70 hover:text-violet-400 transition-colors"
      >
        <Brain className="w-3 h-3" />
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <span>View reasoning ({thoughts.length} step{thoughts.length > 1 ? 's' : ''})</span>
      </button>
      {expanded && (
        <div className="mt-1.5 pl-4 border-l-2 border-violet-500/20 space-y-2">
          {thoughts.map((t, i) => (
            <div key={i} className="text-[11px] text-white/40 leading-relaxed flex gap-2">
              <Lightbulb className="w-3 h-3 text-violet-400/40 shrink-0 mt-0.5" />
              <span>{t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
})

const CodeBlock = memo(({
  language,
  value,
  onCopy,
  onApply,
}: {
  language: string
  value: string
  onCopy?: (t: string) => void
  onApply?: (c: string) => void
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    onCopy?.(value)
  }

  return (
    <div className="my-2 rounded-lg overflow-hidden bg-[#1e1e2e] border border-white/5">
      <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.03] border-b border-white/5">
        <span className="text-[10px] text-white/30 font-mono">{language || 'code'}</span>
        <div className="flex gap-1">
          <button onClick={handleCopy} className="p-1 hover:bg-white/10 rounded text-white/40 hover:text-white transition-colors">
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
          {onApply && (
            <button
              onClick={() => onApply(value)}
              className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-[10px] hover:bg-emerald-500/30 transition-colors"
            >
              Apply
            </button>
          )}
        </div>
      </div>
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: '12px',
          fontSize: '11px',
          lineHeight: '1.5',
          background: 'transparent',
        }}
        wrapLongLines
      >
        {value}
      </SyntaxHighlighter>
    </div>
  )
})

export default memo(function ChatMessage({ role, content, code, onCopy, onApply }: ChatMessageProps) {
  const { thoughts, clean } = role === 'assistant' ? extractThoughts(content) : { thoughts: [], clean: content }

  return (
    <div className={`flex gap-3 ${role === 'user' ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
        role === 'assistant'
          ? 'bg-gradient-to-br from-emerald-500 to-cyan-500'
          : 'bg-purple-500'
      }`}>
        {role === 'assistant' ? <Sparkles className="w-3.5 h-3.5" /> : <span className="text-xs font-medium">U</span>}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${role === 'user' ? 'text-right' : ''}`}>
        {role === 'user' ? (
          <p className="text-sm bg-purple-500/20 inline-block px-3 py-2 rounded-lg text-left whitespace-pre-wrap break-words">
            {clean}
          </p>
        ) : (
          <div className="text-left">
            <ThoughtBubble thoughts={thoughts} />
            <div className="chat-markdown text-sm text-white/80 leading-relaxed">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    const value = String(children).replace(/\n$/, '')
                    if (match || value.includes('\n')) {
                      return <CodeBlock language={match?.[1] || ''} value={value} onCopy={onCopy} onApply={onApply} />
                    }
                    return (
                      <code className="px-1.5 py-0.5 bg-white/10 rounded text-[12px] font-mono text-emerald-300" {...props}>
                        {children}
                      </code>
                    )
                  },
                  p({ children }) {
                    return <p className="mb-2 last:mb-0">{children}</p>
                  },
                  ul({ children }) {
                    return <ul className="list-disc list-inside mb-2 space-y-0.5 text-white/70">{children}</ul>
                  },
                  ol({ children }) {
                    return <ol className="list-decimal list-inside mb-2 space-y-0.5 text-white/70">{children}</ol>
                  },
                  a({ href, children }) {
                    return <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">{children}</a>
                  },
                  blockquote({ children }) {
                    return <blockquote className="border-l-2 border-emerald-500/30 pl-3 my-2 text-white/50 italic">{children}</blockquote>
                  },
                  h1({ children }) { return <h1 className="text-base font-bold mb-1">{children}</h1> },
                  h2({ children }) { return <h2 className="text-sm font-bold mb-1">{children}</h2> },
                  h3({ children }) { return <h3 className="text-sm font-semibold mb-1">{children}</h3> },
                  table({ children }) {
                    return <div className="overflow-x-auto my-2"><table className="text-xs border border-white/10 rounded">{children}</table></div>
                  },
                  th({ children }) { return <th className="px-2 py-1 bg-white/5 text-left text-white/50 border-b border-white/10 text-[11px]">{children}</th> },
                  td({ children }) { return <td className="px-2 py-1 border-b border-white/5 text-[11px]">{children}</td> },
                }}
              >
                {clean}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* Legacy code block (for messages with separate code field) */}
        {code && (
          <CodeBlock language="" value={code} onCopy={onCopy} onApply={onApply} />
        )}
      </div>
    </div>
  )
})
