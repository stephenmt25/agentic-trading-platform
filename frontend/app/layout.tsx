import type { Metadata } from 'next'
import { Chakra_Petch, Share_Tech_Mono } from 'next/font/google'
import './globals.css'
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { AppShell } from "@/components/providers/AppShell";
import { ErrorBoundary } from "@/components/providers/ErrorBoundary";

const chakraPetch = Chakra_Petch({ weight: ["400", "500", "600", "700"], subsets: ['latin'], variable: '--font-sans' });
const shareTechMonoCode = Share_Tech_Mono({ weight: "400", subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'Control Plane Dashboard | Phase 3',
  description: 'Agentic Trading Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={cn("dark", "font-sans", chakraPetch.variable, shareTechMonoCode.variable)}>
      <body className={`${chakraPetch.className} bg-slate-950 text-slate-200 min-h-screen selection:bg-indigo-500/30`}>
        <ErrorBoundary>
          <AuthProvider>
            <AppShell>
              {children}
            </AppShell>
          </AuthProvider>
        </ErrorBoundary>
        <Toaster />
      </body>
    </html>
  )
}
