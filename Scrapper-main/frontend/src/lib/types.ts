export interface PaginationMeta {
  total: number
  limit: number
  offset: number
}

export interface CompanyBrief {
  id: string
  name: string
  primary_domain: string | null
}

export interface Employment {
  id: string
  company_id: string
  title: string | null
  seniority: string | null
  is_current: boolean
  is_c_suite: boolean
  company: CompanyBrief | null
  best_candidate_id?: string | null
  best_candidate_status?: string | null
  best_candidate_score?: number | null
}

export interface ContactCandidate {
  id: string
  person_id: string
  company_id: string
  email: string
  normalized_email: string
  pattern_code: string | null
  generation_source: string | null
  verification_state: string | null
  final_score: number | null
  is_best_current: boolean
}

export interface VerificationEvent {
  id: string
  candidate_id: string
  provider: string
  status: string
  confidence: number | null
  verified_at: string
}

export interface SourceObservation {
  id: string
  source_type: string
  source_url: string | null
  person_id: string | null
  company_id: string | null
  payload: Record<string, unknown>
  observed_at: string
}

export interface PersonListItem {
  id: string
  full_name: string
  linkedin_url: string | null
  headline: string | null
  location: string | null
  current_title: string | null
  current_company_name: string | null
  seniority: string | null
}

export interface PersonDetail {
  id: string
  full_name: string
  first_name: string | null
  last_name: string | null
  linkedin_url: string | null
  headline: string | null
  location: string | null
  raw_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
  employments: Employment[]
  contact_candidates: ContactCandidate[]
  source_observations: SourceObservation[]
}

export interface CompanyEmailPattern {
  id: string
  domain: string
  pattern_code: string
  confidence: number
  evidence_count: number
}

export interface CompanyListItem {
  id: string
  name: string
  primary_domain: string | null
  industry: string | null
  location: string | null
}

export interface CompanyDetail {
  id: string
  name: string
  normalized_name: string | null
  primary_domain: string | null
  website: string | null
  linkedin_url: string | null
  industry: string | null
  location: string | null
  team_size: string | null
  founded_year: number | null
  domain_confidence: number | null
  needs_domain_review: boolean
  raw_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
  people: { id: string; full_name: string; linkedin_url: string | null }[]
  email_patterns: CompanyEmailPattern[]
}

export interface LeadList {
  id: string
  name: string
  description: string | null
  entry_count: number
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  job_type: string
  status: string
  progress_current: number
  progress_total: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  result_summary: Record<string, unknown> | null
  artifact_path?: string | null
}

export interface CandidateGenerated {
  email: string
  pattern_code: string | null
  generation_rank: number
  pattern_confidence: number | null
  final_score: number | null
  verification_state: string | null
  candidate_id: string | null
}

export interface FindAndVerifyResponse {
  person_id: string
  employment_id: string
  company_id: string
  domain: string
  verified: CandidateGenerated[]
  best: CandidateGenerated | null
}
