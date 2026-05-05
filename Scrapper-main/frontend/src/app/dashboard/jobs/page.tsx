'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { getJobs, cancelJob, getJobResultsUrl } from '@/lib/api'
import type { Job } from '@/lib/types'

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued: 'bg-gray-100 text-gray-700',
    running: 'bg-blue-100 text-blue-700',
    succeeded: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-slate-100 text-slate-500',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {status}
    </span>
  )
}

function ProgressBar({ current, total }: { current: number; total: number }) {
  if (total === 0) return <span className="text-slate-400 text-xs">—</span>
  const pct = Math.round((current / total) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-1.5 min-w-[60px]">
        <div
          className="bg-blue-500 h-1.5 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 tabular-nums whitespace-nowrap">
        {current}/{total}
      </span>
    </div>
  )
}

export default function JobsPage() {
  const [filterStatus, setFilterStatus] = useState('')
  const [filterType, setFilterType] = useState('')
  const [page, setPage] = useState(0)
  const limit = 20

  const { data, mutate } = useSWR(
    ['jobs', filterStatus, filterType, page],
    () => getJobs({ status: filterStatus || undefined, job_type: filterType || undefined, limit, offset: page * limit }),
    {
      refreshInterval: (data) => {
        const hasActive = data?.items.some((j: Job) => j.status === 'running' || j.status === 'queued')
        return hasActive ? 3000 : 10000
      },
    }
  )

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this job?')) return
    await cancelJob(id)
    mutate()
  }

  const jobTypes = ['bulk_find_and_verify', 'bulk_verify', 'recheck_person']

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
        <button onClick={() => mutate()} className="text-sm text-slate-500 hover:text-slate-700 border border-gray-200 px-3 py-1.5 rounded">
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(0) }}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded text-slate-700"
        >
          <option value="">All statuses</option>
          {['queued', 'running', 'succeeded', 'failed', 'cancelled'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(0) }}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded text-slate-700"
        >
          <option value="">All types</option>
          {jobTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No jobs found.</div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Type</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Status</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Progress</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Created</th>
                  <th className="px-5 py-3 text-left font-medium text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((job) => (
                  <tr key={job.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-700">{job.job_type}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={job.status} />
                      {job.status === 'running' && (
                        <span className="ml-1 text-xs text-blue-400 animate-pulse">●</span>
                      )}
                      {job.error_message && (
                        <div className="mt-0.5 text-xs text-red-500 max-w-xs truncate" title={job.error_message}>
                          {job.error_message}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 min-w-[140px]">
                      <ProgressBar current={job.progress_current} total={job.progress_total} />
                    </td>
                    <td className="px-5 py-3 text-slate-400 text-xs whitespace-nowrap">
                      {new Date(job.created_at).toLocaleString()}
                      {job.completed_at && (
                        <div className="text-slate-300">
                          done {new Date(job.completed_at).toLocaleString()}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        {job.status === 'succeeded' && (
                          <a
                            href={getJobResultsUrl(job.id)}
                            download
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Download CSV
                          </a>
                        )}
                        {(job.status === 'queued' || job.status === 'running') && (
                          <button
                            onClick={() => handleCancel(job.id)}
                            className="text-xs text-red-500 hover:underline"
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {data.meta.total > limit && (
              <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-slate-600">
                <span>{data.meta.total} total</span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
                  >
                    ← Prev
                  </button>
                  <span className="px-3 py-1 text-slate-500">
                    {page + 1} / {Math.ceil(data.meta.total / limit)}
                  </span>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={(page + 1) * limit >= data.meta.total}
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
