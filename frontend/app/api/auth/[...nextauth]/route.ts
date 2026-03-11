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
      // On initial sign-in, call backend to upsert user and get a backend JWT
      if (account && profile) {
        token.provider = account.provider;
        token.providerAccountId = account.providerAccountId;

        try {
          const res = await fetch(`${BACKEND_URL}/auth/callback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: token.email || profile.email || "",
              name: token.name || profile.name || "",
              image: token.picture || "",
              provider: account.provider,
              provider_account_id: account.providerAccountId,
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
          // Backend may be offline — continue without backend token
          console.error("Backend auth callback error:", err);
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Expose backend token and provider info to the client session
      if (session.user) {
        (session.user as any).provider = token.provider;
        (session.user as any).providerAccountId = token.providerAccountId;
        (session.user as any).backendUserId = token.backendUserId;
      }
      // Attach backend JWT as accessToken so the API client can use it
      (session as any).accessToken = token.backendAccessToken || null;
      return session;
    },
  },
});

export { handler as GET, handler as POST };
