interface Props { role: string; content: string; streaming?: boolean }

export default function ChatMessage({ role, content, streaming }: Props) {
  const isUser = role === 'user'
  return (
    <div style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 8,
    }}>
      <div style={{
        maxWidth: '85%', padding: '8px 12px', borderRadius: 12,
        background: isUser ? '#2563eb' : '#333',
        color: isUser ? '#fff' : '#ddd',
        fontSize: 14, lineHeight: 1.5, whiteSpace: 'pre-wrap',
      }}>
        {!isUser && <span style={{ fontSize: 12, color: '#888' }}>🤖 </span>}
        {content || (streaming ? '思考中...' : '')}
      </div>
    </div>
  )
}
