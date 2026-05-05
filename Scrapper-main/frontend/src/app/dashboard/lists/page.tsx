'use client'

import { useState } from 'react'
import useSWR from 'swr'
import Link from 'next/link'
import { getLists, createList } from '@/lib/api'

export default function ListsPage() {
  const { data: lists, mutate } = useSWR('lists', getLists)

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      await createList(name.trim(), description.trim() || undefined)
      await mutate()
      setName('')
      setDescription('')
      setShowForm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Lists</h1>
        <button
          onClick={() => setShowForm(v => !v)}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : '+ New List'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-5 mb-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">List name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Q2 Fintech Prospects"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded text-slate-800 placeholder-slate-400"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Optional description..."
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded text-slate-800 placeholder-slate-400"
            />
          </div>
          {error && (
            <div className="text-sm text-red-600">{error}</div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!name.trim() || creating}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create List'}
            </button>
          </div>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {!lists ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>
        ) : lists.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">
            No lists yet — create one to start organizing leads.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-5 py-3 text-left font-medium text-slate-500">Name</th>
                <th className="px-5 py-3 text-left font-medium text-slate-500">Description</th>
                <th className="px-5 py-3 text-left font-medium text-slate-500">People</th>
                <th className="px-5 py-3 text-left font-medium text-slate-500">Created</th>
              </tr>
            </thead>
            <tbody>
              {lists.map(list => (
                <tr key={list.id} className="border-b border-gray-50 hover:bg-blue-50">
                  <td className="px-5 py-3">
                    <Link
                      href={`/dashboard/lists/${list.id}`}
                      className="font-medium text-slate-900 hover:text-blue-700"
                    >
                      {list.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-slate-500 text-xs max-w-xs truncate">
                    {list.description ?? '—'}
                  </td>
                  <td className="px-5 py-3 text-slate-600 tabular-nums">{list.entry_count}</td>
                  <td className="px-5 py-3 text-slate-400 text-xs whitespace-nowrap">
                    {new Date(list.created_at).toLocaleDateString()}
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
