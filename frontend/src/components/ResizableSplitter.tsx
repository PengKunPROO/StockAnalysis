// frontend/src/components/ResizableSplitter.tsx
import { useRef, useCallback } from 'react'

interface SplitterProps {
  direction: 'horizontal' | 'vertical'
  onResize: (delta: number) => void
}

export default function ResizableSplitter({ direction, onResize }: SplitterProps) {
  const startPos = useRef(0)
  const dragging = useRef(false)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragging.current = true
    startPos.current = direction === 'horizontal' ? e.clientX : e.clientY
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const current = direction === 'horizontal' ? ev.clientX : ev.clientY
      const delta = current - startPos.current
      startPos.current = current
      onResize(delta)
    }

    const onMouseUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [direction, onResize])

  return (
    <div
      className={direction === 'horizontal' ? 'splitter-h' : 'splitter-v'}
      onMouseDown={onMouseDown}
    />
  )
}
