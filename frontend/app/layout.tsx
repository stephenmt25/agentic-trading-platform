import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Control Plane Dashboard | Phase 1',
  description: 'Agentic Trading Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-200 min-h-screen selection:bg-indigo-500/30`}>
        {/* Navigation Sidebar */}
        <div className="flex h-screen overflow-hidden">
          <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-6 h-full shadow-2xl z-20">
            <div className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400 tracking-tighter mb-12">
              AGENTIC<br /><span className="text-sm text-slate-500 font-normal tracking-widest uppercase">TRADER</span>
            </div>

            <nav className="flex flex-col w-full px-4 space-y-2">
              <a href="/" className="px-4 py-3 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-lg font-bold text-sm tracking-wide transition hover:bg-indigo-500/20">Dashboard</a>
              <a href="/profiles" className="px-4 py-3 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition">Profiles</a>
              <a href="/orders" className="px-4 py-3 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition">Order History</a>
              <a href="/settings" className="px-4 py-3 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition mt-10">Settings</a>
            </nav>
            <div className="mt-auto px-4 w-full">
              <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 flex flex-col text-xs text-slate-400">
                <span className="font-bold mb-1">Status: Active</span>
                <span className="font-mono text-[10px] opacity-70">wss://api/connect</span>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 relative overflow-y-auto w-full h-full p-4 lg:p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
