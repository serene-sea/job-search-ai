import { request } from './auth'

export interface Profile {
  school: string | null
  major: string | null
  degree: string | null
  graduation_year: number | null
  target_roles: string | null
  education_text: string | null
  experience_text: string | null
  updated_at: string | null
}

export type ProfileFields = Omit<Profile, 'updated_at'>

export interface SkillFields {
  name: string
  proficiency: number
  importance: number
  description: string | null
}

export interface Skill extends SkillFields {
  id: number
  updated_at: string
}

export const proficiencyLabels = ['不了解', '了解', '掌握', '熟悉', '完全掌握'] as const
// 数据库存 1–5 方便排序；页面用文字明确从低到高的含义。
export const importanceLabels = ['目前不重要', '较低', '一般重要', '重要', '很重要'] as const

export function loadProfile(): Promise<Profile> {
  return request('/api/profile')
}

export function saveProfile(fields: Partial<ProfileFields>): Promise<Profile> {
  return request('/api/profile', fields, 'PATCH')
}

export function listSkills(): Promise<Skill[]> {
  return request('/api/skills')
}

export function createSkill(fields: SkillFields): Promise<Skill> {
  return request('/api/skills', fields)
}

export function updateSkill(id: number, fields: SkillFields): Promise<Skill> {
  return request(`/api/skills/${id}`, fields, 'PATCH')
}

export function deleteSkill(id: number): Promise<void> {
  return request(`/api/skills/${id}`, {}, 'DELETE')
}
