import type {
  CompanyDetail,
  CompanyListItem,
  ContactCandidate,
  FindAndVerifyResponse,
  Job,
  LeadList,
  PaginationMeta,
  PersonDetail,
  PersonListItem,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ---- People ----
export interface PeopleParams {
  name?: string
  title?: string
  company?: string
  seniority?: string
  limit?: number
  offset?: number
}

export async function getPeople(
  params: PeopleParams = {}
): Promise<{ items: PersonListItem[]; meta: PaginationMeta }> {
  const q = new URLSearchParams()
  if (params.name) q.set('name', params.name)
  if (params.title) q.set('title', params.title)
  if (params.company) q.set('company', params.company)
  if (params.seniority) q.set('seniority', params.seniority)
  q.set('limit', String(params.limit ?? 20))
  q.set('offset', String(params.offset ?? 0))
  return apiFetch(`/api/v1/people?${q}`)
}

export async function getPerson(id: string): Promise<PersonDetail> {
  return apiFetch(`/api/v1/people/${id}`)
}

// ---- Companies ----
export interface CompaniesParams {
  name?: string
  domain?: string
  industry?: string
  limit?: number
  offset?: number
}

export async function getCompanies(
  params: CompaniesParams = {}
): Promise<{ items: CompanyListItem[]; meta: PaginationMeta }> {
  const q = new URLSearchParams()
  if (params.name) q.set('name', params.name)
  if (params.domain) q.set('domain', params.domain)
  if (params.industry) q.set('industry', params.industry)
  q.set('limit', String(params.limit ?? 20))
  q.set('offset', String(params.offset ?? 0))
  return apiFetch(`/api/v1/companies?${q}`)
}

export async function getCompany(id: string): Promise<CompanyDetail> {
  return apiFetch(`/api/v1/companies/${id}`)
}

// ---- Lists ----
export async function getLists(): Promise<LeadList[]> {
  return apiFetch('/api/v1/lists')
}

export async function createList(name: string, description?: string): Promise<LeadList> {
  return apiFetch('/api/v1/lists', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
}

export async function addToList(listId: string, personId: string): Promise<void> {
  await apiFetch(`/api/v1/lists/${listId}/entries`, {
    method: 'POST',
    body: JSON.stringify({ person_id: personId }),
  })
}

export async function removeFromList(listId: string, personId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/lists/${listId}/entries/${personId}`, {
    method: 'DELETE',
  })
  if (!res.ok && res.status !== 204) throw new Error(`${res.status}`)
}

export async function getListEntries(
  listId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<{ items: PersonListItem[]; meta: PaginationMeta }> {
  const q = new URLSearchParams()
  q.set('limit', String(params.limit ?? 50))
  q.set('offset', String(params.offset ?? 0))
  return apiFetch(`/api/v1/lists/${listId}/entries?${q}`)
}

// ---- Jobs ----
export async function getJobs(
  params: { job_type?: string; status?: string; limit?: number; offset?: number } = {}
): Promise<{ items: Job[]; meta: PaginationMeta }> {
  const q = new URLSearchParams()
  if (params.job_type) q.set('job_type', params.job_type)
  if (params.status) q.set('status', params.status)
  q.set('limit', String(params.limit ?? 20))
  q.set('offset', String(params.offset ?? 0))
  return apiFetch(`/api/v1/jobs?${q}`)
}

export async function getJob(id: string): Promise<Job> {
  return apiFetch(`/api/v1/jobs/${id}`)
}

export async function cancelJob(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/jobs/${id}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 204) throw new Error(`${res.status}`)
}

export function getJobResultsUrl(id: string): string {
  return `${BASE}/api/v1/jobs/${id}/results`
}

// ---- Intelligence ----
export async function findAndVerify(
  personId: string,
  employmentId?: string
): Promise<FindAndVerifyResponse> {
  return apiFetch('/api/v1/find-and-verify', {
    method: 'POST',
    body: JSON.stringify({ person_id: personId, employment_id: employmentId ?? null }),
  })
}

export async function recheckPerson(personId: string): Promise<{ job_id: string }> {
  return apiFetch(`/api/v1/recheck/person/${personId}`, { method: 'POST' })
}

// ---- Export ----
export async function exportLeads(body: {
  list_id?: string
  person_ids?: string[]
  format: 'csv' | 'xlsx'
}): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const blob = await res.blob()
  const ext = body.format === 'xlsx' ? 'xlsx' : 'csv'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `sdr_export.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

// ---- Bulk ----
export async function uploadBulkCSV(file: File): Promise<{ job_id: string; total_rows: number }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/api/v1/bulk/find-and-verify`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}
