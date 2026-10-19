import { request } from './auth'

export interface Education {
  id: number
  school: string
  major: string | null
  degree: string | null
  start_year: number | null
  start_month: number | null
  end_year: number | null
  end_month: number | null
  description: string | null
  updated_at: string
}

export type EducationFields = Omit<Education, 'id' | 'updated_at'>

export interface Project {
  id: number
  name: string
  summary: string | null
  source_url: string | null
  highlights: string | null
  updated_at: string
}

export type ProjectFields = Omit<Project, 'id' | 'updated_at'>

export const listEducations = (): Promise<Education[]> => request('/api/educations')
export const createEducation = (fields: EducationFields): Promise<Education> => request('/api/educations', fields)
export const updateEducation = (id: number, fields: EducationFields): Promise<Education> => request(`/api/educations/${id}`, fields, 'PATCH')
export const deleteEducation = (id: number): Promise<void> => request(`/api/educations/${id}`, {}, 'DELETE')

export const listProjects = (): Promise<Project[]> => request('/api/projects')
export const createProject = (fields: ProjectFields): Promise<Project> => request('/api/projects', fields)
export const updateProject = (id: number, fields: ProjectFields): Promise<Project> => request(`/api/projects/${id}`, fields, 'PATCH')
export const deleteProject = (id: number): Promise<void> => request(`/api/projects/${id}`, {}, 'DELETE')
