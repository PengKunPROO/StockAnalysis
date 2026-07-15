interface ChatParams {
  session_id?: string
  skill: string
  message: string
  stock_codes: { code: string; name: string }[]
}

interface ChatEvents {
  onSessionId?: (id: string) => void
  onStatus?: (status: string) => void
  onContent?: (chunk: string) => void
  onDone?: () => void
  onError?: (err: string) => void
}

export async function chatStream(params: ChatParams, events: ChatEvents) {
  let res: Response
  try {
    res = await fetch('/api/v1/diagnosis/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(params),
    })
  } catch (e: any) {
    events.onError?.(e.message || '无法连接到服务器')
    return
  }

  if (!res.ok || !res.body) {
    events.onError?.(`服务器返回错误: ${res.status}`)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedAny = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        // SSE comments (keepalive) start with ":" - skip them
        if (line.startsWith(':')) continue
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            receivedAny = true
            if (data.session_id) events.onSessionId?.(data.session_id)
            if (data.status) events.onStatus?.(data.status)
            if (data.content !== undefined) events.onContent?.(data.content)
            if (data.done) events.onDone?.()
          } catch {
            // Malformed JSON in a data line - skip but don't abort
          }
        }
      }
    }
    // If we never received any meaningful data, report an error
    if (!receivedAny) {
      events.onError?.('服务器未返回任何内容')
    }
  } catch (e: any) {
    // Network error, connection dropped, etc.
    if (e.name === 'AbortError') return
    events.onError?.(e.message || '连接中断')
  }
}
