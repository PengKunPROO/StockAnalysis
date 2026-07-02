import { get, del } from './client'
import type { SkillMeta } from '../types'

export const listSkills = () => get<{ skills: SkillMeta[] }>('/skills')
export const getSkillContent = (name: string) => get<{ name: string; content: string }>(`/skills/${name}`)
export const uploadSkill = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/v1/skills/upload', { method: 'POST', body: form })
  return res.json()
}
export const deleteSkill = (name: string) => del(`/skills/${name}`)
