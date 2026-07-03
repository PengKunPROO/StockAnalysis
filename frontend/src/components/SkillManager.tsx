import { useState, useEffect } from 'react'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props { open: boolean; onClose: () => void; onRefresh: () => void }

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])
  useEffect(() => { if (open) listSkills().then(d => setSkills(d.skills)) }, [open])
  if (!open) return null

  const up = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return
    await uploadSkill(f); setSkills((await listSkills()).skills); onRefresh()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Skill 管理</h2>
          <button className="btn" onClick={onClose} style={{ fontSize: 18, lineHeight: 1 }}>✕</button>
        </div>
        {skills.map(s => (
          <div key={s.name} className="skill-row">
            <div><div className="name">{s.name}</div><div className="desc">{s.description || s.filename}</div></div>
            <button className="btn btn-danger" onClick={async () => { await deleteSkill(s.name); setSkills((await listSkills()).skills); onRefresh() }}>删除</button>
          </div>
        ))}
        {skills.length === 0 && <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 20 }}>暂无 Skill</div>}
        <label className="file-btn">导入 Skill (.md)<input type="file" accept=".md" onChange={up} /></label>
      </div>
    </div>
  )
}
