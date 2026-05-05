'use client'

import { useState } from 'react'
import useSWR from 'swr'
import Link from 'next/link'
import { getPerson, getLists, findAndVerify, recheckPerson, addToList, exportLeads } from '@/lib/api'

function VerifBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-slate-400 text-xs">—</span>
  const colors: Record<string, string> = {
    valid: 'bg-green-100 text-green-800',
    catch_all: 'bg-yellow-100 text-yellow-700',
    unknown: 'bg-gray-100 text-gray-600',
    pending: 'bg-blue-100 text-blue-600',
    invalid: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

function SeniorityBadge({ seniority }: { seniority: string | null }) {
  if (!seniority) return null
  const colors: Record<string, string> = {
    c_suite: 'bg-purple-100 text-purple-800',
    founder: 'bg-purple-100 text-purple-800',
    vp: 'bg-indigo-100 text-indigo-700',
    director: 'bg-blue-100 text-blue-700',
    head: 'bg-sky-100 text-sky-700',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${colors[seniority] ?? 'bg-gray-100 text-gray-600'}`}>
      {seniority.replace('_', '-')}
    </span>
  )
}

export default function PersonDetailPage({ params }: { params: { id: string } }) {
  const { id } = params

  const { data: person, error, mutate } = useSWR(
    ['person', id],
    () => getPerson(id)
  )
  const { data: lists } = useSWR('lists', getLists)

  const [finding, setFinding] = useState(false)
  const [rechecking, setRechecking] = useState(false)
  const [adding, setAdding] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [selectedList, setSelectedList] = useState('')
  const [flash, setFlash] = useState<{ ok: boolean; msg: string } | null>(null)

  function showFlash(ok: boolean, msg: string) {
    setFlash({ ok, msg })
    setTimeout(() => setFlash(null), 5000)
  }

  async function handleFindVerify() {
    if (!person) return
    setFinding(true)
    try {
      const currentEmp = person.employments.find(e => e.is_current) || person.employments[0]
      await findAndVerify(person.id, currentEmp?.id)
      await mutate()
      showFlash(true, 'Find & verify complete — candidates updated')
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Find & verify failed')
    } finally {
      setFinding(false)
    }
  }

  async function handleRecheck() {
    if (!person) return
    setRechecking(true)
    try {
      const { job_id } = await recheckPerson(person.id)
      showFlash(true, `Recheck job queued: ${job_id}`)
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Recheck failed')
    } finally {
      setRechecking(false)
    }
  }

  async function handleAddToList() {
    if (!person || !selectedList) return
    setAdding(true)
    try {
      await addToList(selectedList, person.id)
      showFlash(true, 'Added to list')
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Add to list failed')
    } finally {
      setAdding(false)
    }
  }

  async function handleExport() {
    if (!person) return
    setExporting(true)
    try {
      await exportLeads({ person_ids: [person.id], format: 'csv' })
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  if (!person && !error) {
    return <div className="p-8 text-slate-400 text-sm">Loading...</div>
  }
  if (error) {
    return <div className="p-8 text-red-500 text-sm">Error loading person</div>
  }
  if (!person) return null

  const bestCandidate =
    person.contact_candidates.find(c => c.is_best_current) ||
    [...person.contact_candidates].sort((a, b) => (b.final_score ?? 0) - (a.final_score ?? 0))[0] ||
    null

  const currentEmp = person.employments.find(e => e.is_current) || person.employments[0] || null

  return (
    <div className="p-8 max-w-5xl">
      <Link href="/dashboard/people" className="text-sm text-slate-500 hover:text-slate-700 mb-6 block">
        ← Back to People
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{person.full_name}</h1>
        {currentEmp && (
          <p className="text-slate-600 mt-1 text-sm">
            {currentEmp.title ?? 'Employee'}
            {currentEmp.company && (
              <>
                {' '}@{' '}
                <Link
                  href={`/dashboard/companies/${currentEmp.company_id}`}
                  className="text-blue-600 hover:underline"
                >
                  {currentEmp.company.name}
                </Link>
              </>
            )}
          </p>
        )}
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          {currentEmp && <SeniorityBadge seniority={currentEmp.seniority} />}
          {person.location && <span className="text-xs text-slate-400">{person.location}</span>}
          {person.linkedin_url && (
            <a
              href={person.linkedin_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-500 hover:underline"
            >
              LinkedIn ↗
            </a>
          )}
        </div>
      </div>

      {/* Best email card */}
      {bestCandidate && (
        <div className="bg-white border border-green-200 rounded-lg p-4 mb-4 flex items-center gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wide mb-0.5">Best Email</div>
            <div className="font-mono text-slate-900 font-medium truncate">{bestCandidate.email}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              {bestCandidate.pattern_code && (
                <span>pattern: <code className="bg-slate-100 px-1 rounded">{bestCandidate.pattern_code}</code></span>
              )}
              {bestCandidate.final_score != null && (
                <span>score: <span className="tabular-nums">{bestCandidate.final_score.toFixed(3)}</span></span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <VerifBadge status={bestCandidate.verification_state} />
            {bestCandidate.is_best_current && (
              <span className="text-yellow-500 text-lg" title="Best current candidate">★</span>
            )}
          </div>
        </div>
      )}

      {/* Action bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          onClick={handleFindVerify}
          disabled={finding}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {finding ? 'Working...' : 'Find & Verify'}
        </button>
        <button
          onClick={handleRecheck}
          disabled={rechecking}
          className="px-4 py-2 border border-gray-300 text-slate-700 text-sm rounded hover:bg-gray-50 disabled:opacity-50"
        >
          {rechecking ? 'Queuing...' : 'Recheck'}
        </button>
        <div className="flex items-center gap-1">
          <select
            value={selectedList}
            onChange={e => setSelectedList(e.target.value)}
            className="px-2 py-2 text-sm border border-gray-300 rounded text-slate-700 max-w-[180px]"
          >
            <option value="">Add to list...</option>
            {lists?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
          <button
            onClick={handleAddToList}
            disabled={!selectedList || adding}
            className="px-3 py-2 bg-slate-700 text-white text-sm rounded hover:bg-slate-800 disabled:opacity-50"
          >
            {adding ? '...' : 'Add'}
          </button>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-4 py-2 border border-gray-300 text-slate-700 text-sm rounded hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? 'Exporting...' : 'Export CSV'}
        </button>
      </div>

      {flash && (
        <div
          className={`mb-4 px-4 py-2.5 rounded text-sm border ${
            flash.ok
              ? 'bg-green-50 text-green-800 border-green-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}
        >
          {flash.msg}
        </div>
      )}

      {/* Candidates */}
      <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
          <h2 className="text-sm font-semibold text-slate-700">
            Email Candidates ({person.contact_candidates.length})
          </h2>
        </div>
        {person.contact_candidates.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-sm">
            No candidates yet — click <strong>Find & Verify</strong>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Email</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Pattern</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Status</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Score</th>
                <th className="px-5 py-2.5 text-center font-medium text-slate-500">Best</th>
              </tr>
            </thead>
            <tbody>
              {[...person.contact_candidates]
                .sort((a, b) => (b.final_score ?? 0) - (a.final_score ?? 0))
                .map(c => (
                  <tr key={c.id} className={`border-b border-gray-50 ${c.is_best_current ? 'bg-green-50' : ''}`}>
                    <td className="px-5 py-2.5 font-mono text-xs text-slate-800">{c.email}</td>
                    <td className="px-5 py-2.5 font-mono text-xs text-slate-500">{c.pattern_code ?? '—'}</td>
                    <td className="px-5 py-2.5"><VerifBadge status={c.verification_state} /></td>
                    <td className="px-5 py-2.5 text-xs text-slate-600 tabular-nums">
                      {c.final_score != null ? c.final_score.toFixed(3) : '—'}
                    </td>
                    <td className="px-5 py-2.5 text-center text-yellow-500">
                      {c.is_best_current ? '★' : null}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Employments */}
      {person.employments.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
          <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 className="text-sm font-semibold text-slate-700">Employments</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Company</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Title</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Seniority</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Status</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Email</th>
              </tr>
            </thead>
            <tbody>
              {person.employments.map(emp => (
                <tr key={emp.id} className="border-b border-gray-50">
                  <td className="px-5 py-2.5">
                    {emp.company ? (
                      <Link
                        href={`/dashboard/companies/${emp.company_id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {emp.company.name}
                      </Link>
                    ) : (
                      <span className="text-slate-400 text-xs font-mono">{emp.company_id}</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5 text-slate-600">{emp.title ?? '—'}</td>
                  <td className="px-5 py-2.5"><SeniorityBadge seniority={emp.seniority} /></td>
                  <td className="px-5 py-2.5 text-xs">
                    {emp.is_current ? (
                      <span className="text-green-600 font-medium">current</span>
                    ) : (
                      <span className="text-slate-400">past</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5">
                    <VerifBadge status={emp.best_candidate_status ?? null} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Source Observations — collapsible */}
      {person.source_observations.length > 0 && (
        <details className="bg-white rounded-lg shadow overflow-hidden">
          <summary className="px-5 py-3 text-sm font-semibold text-slate-700 cursor-pointer select-none hover:bg-gray-50 border-b border-gray-100">
            Source Observations ({person.source_observations.length})
          </summary>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Source type</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">URL</th>
                <th className="px-5 py-2.5 text-left font-medium text-slate-500">Observed at</th>
              </tr>
            </thead>
            <tbody>
              {person.source_observations.map(obs => (
                <tr key={obs.id} className="border-b border-gray-50">
                  <td className="px-5 py-2.5 font-mono text-xs text-slate-700">{obs.source_type}</td>
                  <td className="px-5 py-2.5 text-xs text-slate-500 max-w-xs truncate">
                    {obs.source_url ?? '—'}
                  </td>
                  <td className="px-5 py-2.5 text-xs text-slate-400 whitespace-nowrap">
                    {new Date(obs.observed_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}
