import { useState, useEffect } from 'react'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props { open: boolean; onClose: () => void; onRefresh: () => void }

const SRC_COLORS: Record<string, string> = {
  hermes: 'var(--acc)',
  'hermes-builtin': 'var(--muted)',
  uploaded: 'var(--gold)',
  'uploaded (override)': 'var(--up)',
}

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])
  const [filter, setFilter] = useState('all')
  useEffect(() => { if (open) listSkills().then(d => setSkills(d.skills)) }, [open])
  if (!open) return null

  const up = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return
    await uploadSkill(f); setSkills((await listSkills()).skills); onRefresh()
  }

  const filtered = filter === 'all' ? skills : skills.filter(s => s.source === filter)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ width: 520 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Skill 管理</h2>
          <button className="btn" onClick={onClose} style={{ fontSize: 18, lineHeight: 1 }}>✕</button>
        </div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
          {['all', 'hermes', 'uploaded'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              style={{ padding: '2px 10px', borderRadius: 4, border: '1px solid var(--border)', background: filter === f ? 'var(--acc)' : 'transparent', color: filter === f ? '#fff' : 'var(--text)', fontSize: 11, cursor: 'pointer' }}>
              {f === 'all' ? `全部 (${skills.length})` : f === 'hermes' ? `本地Hermes (${skills.filter(s => s.source?.startsWith('hermes')).length})` : `已上传 (${skills.filter(s => s.source === 'uploaded').length})`}
            </button>
          ))}
        </div>
        {filtered.map(s => (
          <div key={s.name} className="skill-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 8px', background: 'var(--surf2)', borderRadius: 4, marginBottom: 4 }}>
            <div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span className="name" style={{ fontSize: 12, color: 'var(--h)', fontWeight: 600 }}>{s.name}</span>
                {s.source && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(41,98,255,.12)', color: SRC_COLORS[s.source] || 'var(--muted)' }}>{s.source}</span>}
              </div>
              <div className="desc" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{s.description?.slice(0, 100) || ''}</div>
            </div>
            {s.source === 'uploaded' && (
              <button className="btn del" onClick={async () => { await deleteSkill(s.name); setSkills((await listSkills()).skills); onRefresh() }} style={{ padding: '2px 8px', fontSize: 10 }}>删除</button>
            )}
          </div>
        ))}
        {filtered.length === 0 && <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 20, fontSize: 12 }}>暂无 Skill</div>}
        <label className="file-btn" style={{ display: 'inline-block', marginTop: 8, padding: '4px 12px', borderRadius: 4, border: '1px solid var(--acc)', color: 'var(--acc)', fontSize: 11, cursor: 'pointer' }}>
          导入 Skill (.md)
          <input type="file" accept=".md" onChange={up} style={{ display: 'none' }} />
        </label>
      </div>
    </div>
  )
}
