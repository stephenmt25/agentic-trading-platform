"use client";

import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

const PUBLIC_PATHS = ["/login"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  useEffect(() => {
    if (status === "loading") return;
    if (!session && !isPublic) {
      router.replace("/login");
    }
  }, [session, status, isPublic, router]);

  // Show nothing while checking auth on protected routes
  if (status === "loading" && !isPublic) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          <p className="text-xs text-slate-600 font-mono uppercase tracking-widest">
            Authenticating...
          </p>
        </div>
      </div>
    );
  }

  // If on a protected route with no session, don't render children
  if (!session && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
