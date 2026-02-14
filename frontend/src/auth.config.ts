
import type { NextAuthConfig } from "next-auth";

export const authConfig = {
  pages: {
    signIn: "/auth/signin",
    verifyRequest: "/auth/verify-request",
    error: "/auth/error",
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnDashboard = nextUrl.pathname.startsWith("/dashboard");
      const isOnSettings = nextUrl.pathname.startsWith("/settings");
      const isOnParties = nextUrl.pathname.startsWith("/parties");

      if (isOnDashboard || isOnSettings || isOnParties) {
        if (isLoggedIn) return true;
        return false; // Redirect to login
      }
      return true;
    },
    session({ session, token }) {
      if (token && session.user) {
        session.user.id = token.sub as string;
      }
      return session;
    },
    jwt({ token, user }) {
        if (user) {
            token.sub = user.id;
        }
        return token;
    }
  },
  providers: [], // Configured in Node-side auth.ts
} satisfies NextAuthConfig;
