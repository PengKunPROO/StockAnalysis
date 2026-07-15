interface ChatParams {
  session_id?: string
  skill: string
  use_skill: boolean
  message: string
  stock_codes: { code: string; name: string }[]
}

interface ChatEvents {
  onSessionId?: (id: string) => void
  onStatus?: (status: string) => void
  onContent?: (chunk: string) => void
  onLog?: (chunk: string) => void
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
    if (!res.ok) {
      events.onError?.(`HTTP ${res.status}`)
      return
    }
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
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          switch (data.type) {
            case 'session': events.onSessionId?.(data.session_id); break
            case 'status': events.onStatus?.(data.status); break
            case 'analysis': events.onContent?.(data.content || ''); break
            case 'log': events.onLog?.(data.content || ''); break
            case 'error': events.onError?.(data.content || 'Unknown error'); break
            case 'done': events.onDone?.(); break
          }
        } catch {}
      }
    }
  } catch (e: any) {
    events.onError?.(e.message || 'Connection error')
  }
}
