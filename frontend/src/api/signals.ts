import { get } from './client'
import type { SignalsPayload } from '../types'

export const getSignals = (code: string, days = 90) =>
  get<SignalsPayload>(`/signals/${code}?days=${days}`)

interface AiEvents {
  onSignals?: (payload: SignalsPayload) => void
  onContent?: (chunk: string) => void
  onError?: (msg: string) => void
  onDone?: () => void
}

export async function streamSignalsAI(code: string, events: AiEvents, days = 90) {
  try {
    const res = await fetch(`/api/v1/signals/${code}/ai?days=${days}`, { method: 'POST' })
    if (!res.ok || !res.body) {
      events.onError?.(`请求失败 (${res.status})`)
      return
    }
    const reader = res.body.getReader()
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
          if (data.type === 'signals') events.onSignals?.(data.data)
          else if (data.type === 'content') events.onContent?.(data.content)
          else if (data.type === 'error') events.onError?.(data.content)
          else if (data.type === 'done') events.onDone?.()
        } catch {}
      }
    }
    events.onDone?.()
  } catch (e: any) {
    events.onError?.(e.message || '连接错误')
  }
}
