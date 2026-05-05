'use client'

import { useState } from 'react'
import useSWR from 'swr'
import Link from 'next/link'
import { getLists, getListEntries, removeFromList, exportLeads } from '@/lib/api'

const LIMIT = 50

export default function ListDetailPage({ params }: { params: { id: string } }) {
  const { id } = params
  const [page, setPage] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [flash, setFlash] = useState<{ ok: boolean; msg: string } | null>(null)

  const { data: lists } = useSWR('lists', getLists)
  const { data, mutate } = useSWR(
    ['list-entries', id, page],
    () => getListEntries(id, { limit: LIMIT, offset: page * LIMIT })
  )

  const list = lists?.find(l => l.id === id)

  function showFlash(ok: boolean, msg: string) {
    setFlash({ ok, msg })
    setTimeout(() => setFlash(null), 4000)
  }

  async function handleRemove(personId: string, name: string) {
    if (!confirm(`Remove ${name} from this list?`)) return
    try {
      await removeFromList(id, personId)
      await mutate()
      showFlash(true, `Removed ${name}`)
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Remove failed')
    }
  }

  async function handleExport(format: 'csv' | 'xlsx') {
    setExporting(true)
    try {
      await exportLeads({ list_id: id, format })
    } catch (e) {
      showFlash(false, e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="p-8 max-w-5xl">
      <Link href="/dashboard/lists" className="text-sm text-slate-500 hover:text-slate-700 mb-6 block">
        ← Back to Lists
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {list?.name ?? 'List'}
          </h1>
          {list?.description && (
            <p className="text-sm text-slate-500 mt-1">{list.description}</p>
          )}
          {data && (
            <p className="text-sm text-slate-400 mt-1">{data.meta.total} people</p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting}
            className="px-3 py-2 border border-gray-300 text-slate-700 text-sm rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport('xlsx')}
            disabled={exporting}
            className="px-3 py-2 border border-gray-300 text-slate-700 text-sm rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Export XLSX
          </button>
        </div>
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

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">
            No people in this list yet — add them from the{' '}
            <Link href="/dashboard/people" className="text-blue-600 hover:underline">
              People page
            </Link>
            .
          </div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Name</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Title</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Company</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Seniority</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Location</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {data.items.map(person => (
                  <tr key={person.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <Link
                        href={`/dashboard/people/${person.id}`}
                        className="font-medium text-slate-900 hover:text-blue-700"
                      >
                        {person.full_name}
                      </Link>
                      {person.linkedin_url && (
                        <div className="text-xs text-slate-400 truncate max-w-[180px]">
                          {person.linkedin_url}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{person.current_title ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-600">{person.current_company_name ?? '—'}</td>
                    <td className="px-5 py-3">
                      {person.seniority && (
                        <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                          {person.seniority.replace('_', '-')}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-slate-500 text-xs">{person.location ?? '—'}</td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => handleRemove(person.id, person.full_name)}
                        className="text-xs text-red-500 hover:underline"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data.meta.total > LIMIT && (
              <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-slate-600">
                <span>
                  {data.meta.total.toLocaleString()} total · showing{' '}
                  {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, data.meta.total)}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
                  >
                    ← Prev
                  </button>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={(page + 1) * LIMIT >= data.meta.total}
                    className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
