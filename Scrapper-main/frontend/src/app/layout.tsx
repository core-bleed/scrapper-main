import type { Metadata } from 'next'
import NavLinks from '@/components/NavLinks'
import './globals.css'

export const metadata: Metadata = {
  title: 'SDR Intel',
  description: 'Outbound intelligence platform',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen bg-gray-50">
        {/* Sidebar */}
        <aside className="w-56 flex-shrink-0 bg-slate-900 text-white flex flex-col">
          <div className="px-4 py-5 border-b border-slate-700">
            <span className="text-lg font-bold tracking-tight">SDR Intel</span>
          </div>
          <nav className="flex-1 px-2 py-4 space-y-1">
            <NavLinks />
          </nav>
          <div className="px-4 py-3 border-t border-slate-700 text-xs text-slate-500">
            Single operator · localhost
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </body>
    </html>
  )
}
