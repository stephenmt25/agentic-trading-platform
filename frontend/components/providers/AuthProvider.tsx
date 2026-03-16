"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/authStore";

function SessionSync({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const setSession = useAuthStore((s) => s.setSession);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    if (status === "loading") return;

    if (session?.accessToken) {
      setSession(
        session.accessToken as string,
        session.user?.name ?? session.user?.email ?? null
      );
    } else {
      logout();
    }
  }, [session, status, setSession, logout]);

  return <>{children}</>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <SessionSync>{children}</SessionSync>
    </SessionProvider>
  );
}
