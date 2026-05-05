'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const navLinks = [
  { href: '/dashboard', label: 'Dashboard', icon: '⬡', exact: true },
  { href: '/dashboard/people', label: 'People', icon: '👤', exact: false },
  { href: '/dashboard/companies', label: 'Companies', icon: '🏢', exact: false },
  { href: '/dashboard/lists', label: 'Lists', icon: '📋', exact: false },
  { href: '/dashboard/bulk', label: 'Bulk Upload', icon: '⬆', exact: false },
  { href: '/dashboard/jobs', label: 'Jobs', icon: '⚙', exact: false },
]

export default function NavLinks() {
  const pathname = usePathname()
  return (
    <>
      {navLinks.map((link) => {
        const isActive = link.exact
          ? pathname === link.href
          : pathname === link.href || pathname.startsWith(link.href + '/')
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              isActive
                ? 'bg-slate-700 text-white'
                : 'text-slate-300 hover:bg-slate-700 hover:text-white'
            }`}
          >
            <span>{link.icon}</span>
            <span>{link.label}</span>
          </Link>
        )
      })}
    </>
  )
}
