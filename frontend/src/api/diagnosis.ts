interface ChatParams {
  session_id?: string
  skill: string
  message: string
  stock_codes: { code: string; name: string }[]
}

interface ChatEvents {
  onSessionId?: (id: string) => void
  onContent?: (chunk: string) => void
  onDone?: () => void
  onError?: (err: string) => void
}

export async function chatStream(params: ChatParams, events: ChatEvents) {
  try {
    const res = await fetch('/api/v1/diagnosis/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.session_id) events.onSessionId?.(data.session_id)
            if (data.content !== undefined) events.onContent?.(data.content)
            if (data.done) events.onDone?.()
          } catch {}
        }
      }
    }
  } catch (e: any) {
    events.onError?.(e.message || 'Connection error')
  }
}
