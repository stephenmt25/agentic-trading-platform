import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    accessToken?: string | null;
    user: {
      name?: string | null;
      email?: string | null;
      image?: string | null;
      provider?: string;
      providerAccountId?: string;
      backendUserId?: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    provider?: string;
    providerAccountId?: string;
    idToken?: string;
    backendAccessToken?: string;
    backendUserId?: string;
  }
}
