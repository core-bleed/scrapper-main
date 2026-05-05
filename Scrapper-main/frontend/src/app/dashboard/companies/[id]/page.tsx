'use client'

import useSWR from 'swr'
import Link from 'next/link'
import { getCompany } from '@/lib/api'

export default function CompanyDetailPage({ params }: { params: { id: string } }) {
  const { id } = params
  const { data: company, error } = useSWR(['company', id], () => getCompany(id))

  if (!company && !error) {
    return <div className="p-8 text-slate-400 text-sm">Loading...</div>
  }
  if (error) {
    return <div className="p-8 text-red-500 text-sm">Error loading company</div>
  }
  if (!company) return null

  return (
    <div className="p-8 max-w-5xl">
      <Link href="/dashboard/companies" className="text-sm text-slate-500 hover:text-slate-700 mb-6 block">
        ← Back to Companies
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{company.name}</h1>
        {company.primary_domain && (
          <p className="font-mono text-slate-500 text-sm mt-1">{company.primary_domain}</p>
        )}
        <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-500">
          {company.industry && <span>{company.industry}</span>}
          {company.location && <span>{company.location}</span>}
          {company.team_size && <span>Team: {company.team_size}</span>}
          {company.founded_year && <span>Founded: {company.founded_year}</span>}
          {company.website && (
            <a href={company.website} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">
              Website ↗
            </a>
          )}
          {company.linkedin_url && (
            <a href={company.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">
              LinkedIn ↗
            </a>
          )}
        </div>
        {company.domain_confidence != null && (
          <div className="flex items-center gap-2 mt-3">
            <span className="text-xs text-slate-400">Domain confidence:</span>
            <div className="w-24 bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-blue-500 h-1.5 rounded-full"
                style={{ width: `${Math.round(company.domain_confidence * 100)}%` }}
              />
            </div>
            <span className="text-xs text-slate-500 tabular-nums">
              {(company.domain_confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {company.needs_domain_review && (
        <div className="mb-4 px-4 py-2.5 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
          Domain needs review — confidence may be low
        </div>
      )}

      {/* Email Patterns */}
      {company.email_patterns.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
          <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 className="text-sm font-semibold text-slate-700">
              Email Patterns ({company.email_patterns.length})
            </h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Pattern</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Confidence</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Evidence</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Domain</th>
              </tr>
            </thead>
            <tbody>
              {[...company.email_patterns]
                .sort((a, b) => b.confidence - a.confidence)
                .map(p => (
                  <tr key={p.id} className="border-b border-gray-50">
                    <td className="px-5 py-2.5 font-mono text-xs text-slate-800">{p.pattern_code}</td>
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5">
                          <div
                            className="bg-blue-500 h-1.5 rounded-full"
                            style={{ width: `${Math.round(p.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 tabular-nums">
                          {(p.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-2.5 text-xs text-slate-500 tabular-nums">{p.evidence_count}</td>
                    <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{p.domain}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* People */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
          <h2 className="text-sm font-semibold text-slate-700">
            People ({company.people.length})
          </h2>
        </div>
        {company.people.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-sm">No people associated yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Name</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">LinkedIn</th>
              </tr>
            </thead>
            <tbody>
              {company.people.map(person => (
                <tr key={person.id} className="border-b border-gray-50 hover:bg-blue-50">
                  <td className="px-5 py-2.5">
                    <Link
                      href={`/dashboard/people/${person.id}`}
                      className="font-medium text-slate-900 hover:text-blue-700"
                    >
                      {person.full_name}
                    </Link>
                  </td>
                  <td className="px-5 py-2.5 text-xs text-slate-400 truncate max-w-xs">
                    {person.linkedin_url ? (
                      <a href={person.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">
                        {person.linkedin_url}
                      </a>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
