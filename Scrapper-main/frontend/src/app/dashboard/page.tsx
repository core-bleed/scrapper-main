'use client'

import useSWR from 'swr'
import Link from 'next/link'
import { getPeople, getCompanies, getLists, getJobs } from '@/lib/api'
import type { Job } from '@/lib/types'

function StatCard({ label, value, href }: { label: string; value: number | undefined; href: string }) {
  return (
    <Link href={href} className="block bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow">
      <div className="text-3xl font-bold text-slate-900">{value?.toLocaleString() ?? '—'}</div>
      <div className="text-sm text-slate-500 mt-1">{label}</div>
    </Link>
  )
}

function JobStatusBadge({ status }: { status: string }) {
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

export default function DashboardPage() {
  const { data: people } = useSWR('dash-people', () => getPeople({ limit: 1 }))
  const { data: companies } = useSWR('dash-companies', () => getCompanies({ limit: 1 }))
  const { data: lists } = useSWR('dash-lists', getLists)
  const { data: jobs, mutate: mutateJobs } = useSWR(
    'dash-jobs',
    () => getJobs({ limit: 8 }),
    {
      refreshInterval: (data) => {
        const hasActive = data?.items.some((j: Job) => j.status === 'running' || j.status === 'queued')
        return hasActive ? 3000 : 15000
      },
    }
  )

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="People" value={people?.meta.total} href="/dashboard/people" />
        <StatCard label="Companies" value={companies?.meta.total} href="/dashboard/companies" />
        <StatCard label="Lists" value={lists?.length} href="/dashboard/lists" />
        <StatCard label="Total Jobs" value={jobs?.meta.total} href="/dashboard/jobs" />
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Recent Jobs</h2>
          <div className="flex gap-3">
            <button
              onClick={() => mutateJobs()}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              Refresh
            </button>
            <Link href="/dashboard/jobs" className="text-xs text-blue-600 hover:underline">
              View all →
            </Link>
          </div>
        </div>
        {!jobs ? (
          <div className="px-6 py-8 text-center text-slate-400 text-sm">Loading...</div>
        ) : jobs.items.length === 0 ? (
          <div className="px-6 py-8 text-center text-slate-500 text-sm">
            No jobs yet —{' '}
            <Link href="/dashboard/bulk" className="text-blue-600 hover:underline">
              upload a CSV
            </Link>{' '}
            to get started.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-6 py-3 text-left font-medium text-slate-500">Type</th>
                <th className="px-6 py-3 text-left font-medium text-slate-500">Status</th>
                <th className="px-6 py-3 text-left font-medium text-slate-500">Progress</th>
                <th className="px-6 py-3 text-left font-medium text-slate-500">Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.items.map((job) => (
                <tr key={job.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-6 py-3 font-mono text-xs text-slate-700">{job.job_type}</td>
                  <td className="px-6 py-3">
                    <JobStatusBadge status={job.status} />
                    {job.status === 'running' && (
                      <span className="ml-2 text-xs text-slate-400 animate-pulse">●</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-slate-600">
                    {job.progress_total > 0
                      ? `${job.progress_current} / ${job.progress_total}`
                      : '—'}
                  </td>
                  <td className="px-6 py-3 text-slate-400 text-xs">
                    {new Date(job.created_at).toLocaleString()}
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
