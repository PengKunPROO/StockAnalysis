import { useState, useEffect } from 'react'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  onRefresh: () => void
}

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])

  useEffect(() => {
    if (open) listSkills().then(d => setSkills(d.skills))
  }, [open])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await uploadSkill(file)
    const d = await listSkills()
    setSkills(d.skills)
    onRefresh()
  }

  const handleDelete = async (name: string) => {
    await deleteSkill(name)
    const d = await listSkills()
    setSkills(d.skills)
    onRefresh()
  }

  if (!open) return null

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 200,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#2a2a3e', borderRadius: 12, padding: 20,
        width: 480, maxHeight: '80vh', overflow: 'auto',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ fontSize: 18, fontWeight: 600 }}>Skill 管理</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 20 }}>✕</button>
        </div>

        {skills.map(s => (
          <div key={s.name} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '8px 12px', background: '#333', borderRadius: 8, marginBottom: 8,
          }}>
            <div>
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div style={{ color: '#888', fontSize: 12 }}>{s.description || s.filename}</div>
            </div>
            <button onClick={() => handleDelete(s.name)} style={{
              background: '#c0392b', color: '#fff', border: 'none', borderRadius: 4,
              padding: '4px 10px', cursor: 'pointer', fontSize: 12,
            }}>删除</button>
          </div>
        ))}

        {skills.length === 0 && (
          <div style={{ color: '#666', textAlign: 'center', padding: 20 }}>暂无 Skill，请导入</div>
        )}

        <label style={{
          display: 'block', marginTop: 16, padding: '10px 16px',
          background: '#2563eb', color: '#fff', borderRadius: 8,
          textAlign: 'center', cursor: 'pointer', fontSize: 14,
        }}>
          导入 Skill (.md 文件)
          <input type="file" accept=".md" onChange={handleUpload}
            style={{ display: 'none' }} />
        </label>
      </div>
    </div>
  )
}
