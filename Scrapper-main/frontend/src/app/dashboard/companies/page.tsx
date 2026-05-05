'use client'

import { useState } from 'react'
import useSWR from 'swr'
import Link from 'next/link'
import { getCompanies } from '@/lib/api'

const LIMIT = 50

export default function CompaniesPage() {
  const [nameQ, setNameQ] = useState('')
  const [domainQ, setDomainQ] = useState('')
  const [industryQ, setIndustryQ] = useState('')
  const [page, setPage] = useState(0)
  const [applied, setApplied] = useState({ name: '', domain: '', industry: '' })

  const { data, error } = useSWR(
    ['companies', applied, page],
    () => getCompanies({
      name: applied.name || undefined,
      domain: applied.domain || undefined,
      industry: applied.industry || undefined,
      limit: LIMIT,
      offset: page * LIMIT,
    })
  )

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(0)
    setApplied({ name: nameQ, domain: domainQ, industry: industryQ })
  }

  const handleClear = () => {
    setNameQ(''); setDomainQ(''); setIndustryQ('')
    setPage(0)
    setApplied({ name: '', domain: '', industry: '' })
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Companies</h1>
        {data && <span className="text-sm text-slate-500">{data.meta.total.toLocaleString()} total</span>}
      </div>

      <form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="grid grid-cols-3 gap-3">
          <input
            type="text" placeholder="Company name..." value={nameQ}
            onChange={(e) => setNameQ(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded text-slate-800 placeholder-slate-400"
          />
          <input
            type="text" placeholder="Domain (e.g. acme.com)..." value={domainQ}
            onChange={(e) => setDomainQ(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded text-slate-800 placeholder-slate-400"
          />
          <input
            type="text" placeholder="Industry..." value={industryQ}
            onChange={(e) => setIndustryQ(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded text-slate-800 placeholder-slate-400"
          />
        </div>
        <div className="flex gap-2 mt-3">
          <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">Search</button>
          <button type="button" onClick={handleClear} className="px-4 py-1.5 text-slate-600 text-sm border border-gray-300 rounded hover:bg-gray-50">Clear</button>
        </div>
      </form>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {!data && !error ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-500 text-sm">Error loading companies</div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No companies found.</div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Company</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Domain</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Industry</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Location</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((company) => (
                  <tr key={company.id} className="border-b border-gray-50 hover:bg-blue-50">
                    <td className="px-5 py-3">
                      <Link href={`/dashboard/companies/${company.id}`} className="font-medium text-slate-900 hover:text-blue-700">
                        {company.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-600">{company.primary_domain ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-500">{company.industry ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-500 text-xs">{company.location ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data.meta.total > LIMIT && (
              <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-slate-600">
                <span>{data.meta.total.toLocaleString()} total</span>
                <div className="flex gap-2">
                  <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                    className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50">← Prev</button>
                  <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * LIMIT >= data.meta.total}
                    className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50">Next →</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
