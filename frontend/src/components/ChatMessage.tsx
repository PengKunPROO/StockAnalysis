import { useMemo } from 'react'

interface Props { role: string; content: string; streaming?: boolean }

function renderMd(text: string): string {
  let html = text
    // escape HTML
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // headers
    .replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;color:#f0c040">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin:12px 0 6px;color:#f0c040">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin:14px 0 8px;color:#f0c040">$1</h2>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // inline code
    .replace(/`([^`]+)`/g, '<code style="background:#444;padding:1px 4px;border-radius:3px">$1</code>')
    // table separators
    .replace(/^\|[-:\s|]+\|$/gm, '')
    // table rows
    .replace(/^\|(.+)\|$/gm, (_, cells) => {
      const tds = cells.split('|').map((c: string) => 
        `<td style="padding:2px 8px;border:1px solid #555">${c.trim()}</td>`
      ).join('')
      return `<tr>${tds}</tr>`
    })
    // wrap consecutive trs in table
    .replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table style="border-collapse:collapse;margin:8px 0;font-size:13px">$1</table>')
    // bullet points
    .replace(/^- (.+)$/gm, '<li style="margin:2px 0">$1</li>')
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul style="margin:4px 0;padding-left:20px">$1</ul>')
    // blockquote
    .replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:3px solid #f0c040;padding:4px 12px;margin:8px 0;color:#ccc;background:#2a2a2a;border-radius:0 6px 6px 0">$1</blockquote>')
    // line breaks
    .replace(/\n/g, '<br/>')

  return html
}

export default function ChatMessage({ role, content, streaming }: Props) {
  const isUser = role === 'user'
  const html = useMemo(() => isUser ? content : renderMd(content), [content, isUser])

  return (
    <div style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 8,
    }}>
      <div style={{
        maxWidth: isUser ? '85%' : '95%',
        padding: '8px 12px', borderRadius: 12,
        background: isUser ? '#2563eb' : '#333',
        color: isUser ? '#fff' : '#ddd',
        fontSize: 14, lineHeight: 1.5,
        overflowX: 'auto',
      }}
        dangerouslySetInnerHTML={{ __html: isUser ? content : html }}
      />
    </div>
  )
}
