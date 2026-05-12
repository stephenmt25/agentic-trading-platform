import type { Metadata, Viewport } from 'next'
import { IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google'
import './globals.css'
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { AppShell } from "@/components/providers/AppShell";
import { ErrorBoundary } from "@/components/providers/ErrorBoundary";
import { ModeProvider } from "@/components/providers/ModeProvider";

const ibmPlexSans = IBM_Plex_Sans({ weight: ["400", "500", "600", "700"], subsets: ['latin'], variable: '--font-sans' });
const ibmPlexMono = IBM_Plex_Mono({ weight: ["400", "500", "600"], subsets: ['latin'], variable: '--font-mono' });

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

export const metadata: Metadata = {
  title: 'Praxis Trading Platform',
  description: 'Agentic Trading Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-mode="hot" className={cn("dark", ibmPlexSans.variable, ibmPlexMono.variable)}>
      <body className={`${ibmPlexSans.className} bg-background text-foreground min-h-screen selection:bg-primary/20`}>
        <ErrorBoundary>
          <AuthProvider>
            <AppShell>
              <ModeProvider>
                {children}
              </ModeProvider>
            </AppShell>
          </AuthProvider>
        </ErrorBoundary>
        <Toaster />
      </body>
    </html>
  )
}
