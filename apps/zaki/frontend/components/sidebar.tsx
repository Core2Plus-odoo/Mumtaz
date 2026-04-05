'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, ArrowLeftRight, Upload, Bot, Settings, LogOut, Zap } from 'lucide-react'

const nav = [
  { href: '/',              label: 'Dashboard',    icon: LayoutDashboard },
  { href: '/ai',            label: 'ZAKI AI',      icon: Bot },
  { href: '/transactions',  label: 'Transactions', icon: ArrowLeftRight },
  { href: '/upload',        label: 'Upload Data',  icon: Upload },
  { href: '/settings',      label: 'Settings',     icon: Settings },
]

export default function Sidebar() {
  const path = usePathname()

  function logout() {
    localStorage.removeItem('zaki_token')
    localStorage.removeItem('zaki_user')
    window.location.href = '/login'
  }

  return (
    <aside className="w-56 shrink-0 bg-zaki-surface border-r border-zaki-border flex flex-col h-screen sticky top-0">
      {/* Brand */}
      <div className="p-5 border-b border-zaki-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center zaki-glow-sm">
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">ZAKI</div>
            <div className="text-xs text-purple-400">CFO AI</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path === href
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-600/30'
                  : 'text-zaki-muted hover:text-white hover:bg-zaki-card'
              }`}>
              <Icon size={16} className={active ? 'text-purple-400' : ''} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t border-zaki-border">
        <button onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-zaki-muted hover:text-red-400 hover:bg-red-400/10 w-full transition-all">
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
