import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import GitHubProvider from "next-auth/providers/github";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID ?? "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET ?? "",
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      // On initial sign-in, capture provider info and ID token
      if (account && profile) {
        token.provider = account.provider;
        token.providerAccountId = account.providerAccountId;
        token.email = token.email || profile.email || "";
        token.name = token.name || profile.name || "";
        // Store the OAuth id_token for backend verification
        token.idToken = account.id_token || "";
      }

      // Get backend token if we don't have one yet (initial sign-in or retry)
      if (!token.backendAccessToken && token.email) {
        try {
          // Encode a session token signed with NEXTAUTH_SECRET for backend verification
          const jwt = await import("next-auth/jwt");
          const sessionToken = await (jwt as any).encode({
            token: { email: token.email, sub: token.sub },
            secret: process.env.NEXTAUTH_SECRET || "",
          });

          const res = await fetch(`${BACKEND_URL}/auth/callback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: token.email,
              name: token.name || "",
              image: token.picture || "",
              provider: token.provider || "google",
              provider_account_id: token.providerAccountId || "",
              id_token: sessionToken,
            }),
          });

          if (res.ok) {
            const data = await res.json();
            token.backendAccessToken = data.access_token;
            token.backendUserId = data.user_id;
          } else {
            console.error("Backend auth callback failed:", res.status);
          }
        } catch (err) {
          // Backend may be offline — will retry on next session refresh
          console.error("Backend auth callback error:", err);
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Expose backend token and provider info to the client session
      if (session.user) {
        session.user.provider = token.provider;
        session.user.providerAccountId = token.providerAccountId;
        session.user.backendUserId = token.backendUserId;
      }
      // Attach backend JWT as accessToken so the API client can use it
      session.accessToken = token.backendAccessToken || null;
      return session;
    },
  },
});

export { handler as GET, handler as POST };
