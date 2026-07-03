import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props { open: boolean; onClose: () => void; onRefresh: () => void }

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])
  useEffect(() => { if (open) listSkills().then(d => setSkills(d.skills)) }, [open])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return
    await uploadSkill(f)
    const d = await listSkills(); setSkills(d.skills); onRefresh()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader><DialogTitle>Skill 管理</DialogTitle></DialogHeader>
        {skills.map(s => (
          <div key={s.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <div className="font-semibold text-sm">{s.name}</div>
              <div className="text-xs text-muted">{s.description || s.filename}</div>
            </div>
            <Button
              variant="destructive" size="sm"
              onClick={async () => { await deleteSkill(s.name); const d = await listSkills(); setSkills(d.skills); onRefresh() }}
              title="删除此 Skill"
            >
              删除
            </Button>
          </div>
        ))}
        {skills.length === 0 && <div className="text-center text-muted py-8">暂无 Skill，请导入</div>}
        <label className="block w-full cursor-pointer">
          <Button variant="default" className="w-full" asChild>
            <span>导入 Skill (.md)</span>
          </Button>
          <input type="file" accept=".md" onChange={handleUpload} className="hidden" />
        </label>
      </DialogContent>
    </Dialog>
  )
}
