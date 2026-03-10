import type { Metadata } from 'next'
import { Inter, Geist } from 'next/font/google'
import './globals.css'
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";
import { AlertTray } from "@/components/validation/AlertTray";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

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
    <html lang="en" className={cn("dark", "font-sans", geist.variable)}>
      <body className={`${inter.className} bg-slate-950 text-slate-200 min-h-screen selection:bg-indigo-500/30`}>
        {/* Navigation Sidebar */}
        <div className="flex h-screen overflow-hidden">
          <aside className="w-64 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-6 h-full shadow-2xl z-20">
            <div className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400 tracking-tighter mb-12">
              AGENTIC<br /><span className="text-sm text-slate-500 font-normal tracking-widest uppercase">TRADER</span>
            </div>

            <nav className="flex flex-col w-full px-4 space-y-2">
              <a href="/" className="px-4 py-3 bg-primary/10 text-primary border border-primary/20 rounded-lg font-bold text-sm tracking-wide transition hover:bg-primary/20">Dashboard</a>
              <a href="/profiles" className="px-4 py-3 text-muted-foreground hover:text-foreground hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition">Profiles</a>
              <a href="/paper-trading" className="px-4 py-3 text-muted-foreground hover:text-foreground hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition">Paper Trading</a>
              <a href="/settings" className="px-4 py-3 text-muted-foreground hover:text-foreground hover:bg-slate-800/50 rounded-lg font-bold text-sm tracking-wide transition mt-10">Settings</a>
            </nav>
          </aside>

          {/* Main Area Wrapper */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
            
            {/* Top Global Header */}
            <header className="h-16 px-4 lg:px-8 border-b border-border bg-card flex items-center justify-between shrink-0 shadow-sm z-30">
              <div className="flex items-center gap-4">
                {/* Space for future breadcrumbs or mobile menu toggle */}
              </div>
              
              <div className="flex items-center gap-6">
                {/* Connection Status Indicator */}
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-black/20 border border-border rounded-full text-xs text-muted-foreground">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span className="font-mono uppercase font-bold text-[10px] tracking-widest text-emerald-500/80">Active</span>
                  <span className="font-mono opacity-50 ml-1">wss://api/connect</span>
                </div>

                {/* Global Notification Tray */}
                <AlertTray />
                
                {/* User Avatar Placeholder */}
                <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 cursor-pointer hover:bg-slate-700 hover:text-white transition-colors">
                  AD
                </div>
              </div>
            </header>

            {/* Scrollable Page Content */}
            <main className="flex-1 relative overflow-y-auto w-full h-full p-4 lg:p-8">
              {children}
            </main>
          </div>
        </div>
        <Toaster />
      </body>
    </html>
  )
}
