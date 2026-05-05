'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { uploadBulkCSV } from '@/lib/api'

export default function BulkPage() {
  const router = useRouter()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ job_id: string; total_rows: number } | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) { setError('Select a CSV file first'); return }
    setUploading(true)
    setError(null)
    setResult(null)
    try {
      const res = await uploadBulkCSV(file)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Bulk Upload</h1>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="font-semibold text-slate-800 mb-3">CSV Format</h2>
        <p className="text-sm text-slate-600 mb-3">
          Upload a CSV to run find-and-verify on a batch of people. Required columns:
        </p>
        <div className="bg-slate-50 rounded p-3 font-mono text-xs text-slate-700 mb-4">
          full_name, company_name[, company_domain, title, first_name, last_name, linkedin_url]
        </div>
        <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside">
          <li><code className="bg-slate-100 px-1 rounded">full_name</code> — required</li>
          <li><code className="bg-slate-100 px-1 rounded">company_name</code> or <code className="bg-slate-100 px-1 rounded">company_domain</code> — at least one required</li>
          <li>All other columns are optional enrichment hints</li>
          <li>Maximum 1,000 rows per upload</li>
        </ul>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              CSV File
            </label>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="block w-full text-sm text-slate-700 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 file:font-medium hover:file:bg-blue-100"
            />
          </div>

          {error && (
            <div className="px-4 py-3 bg-red-50 text-red-700 rounded text-sm border border-red-200">
              {error}
            </div>
          )}

          {result && (
            <div className="px-4 py-3 bg-green-50 text-green-800 rounded text-sm border border-green-200">
              <p className="font-medium">Job queued successfully</p>
              <p className="mt-1">Processing {result.total_rows} rows · Job ID: <span className="font-mono text-xs">{result.job_id}</span></p>
              <button
                type="button"
                onClick={() => router.push('/dashboard/jobs')}
                className="mt-2 text-green-700 underline text-xs"
              >
                Track progress in Jobs →
              </button>
            </div>
          )}

          <button
            type="submit"
            disabled={uploading}
            className="px-6 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Upload & Start Job'}
          </button>
        </form>
      </div>
    </div>
  )
}
