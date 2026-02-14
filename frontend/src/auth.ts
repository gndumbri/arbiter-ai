import NextAuth from "next-auth";
// import { DrizzleAdapter } from "@auth/drizzle-adapter";
// import { db } from "@/db";
// import { accounts, users, verificationTokens } from "@/db/auth-schema";
// import Email from "next-auth/providers/email";
import { authConfig } from "./auth.config";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  // adapter: DrizzleAdapter(db, {
  //   usersTable: users,
  //   accountsTable: accounts,
  //   // sessionsTable not needed for JWT strategy
  //   verificationTokensTable: verificationTokens,
  // }),
  session: { strategy: "jwt" },
  providers: [
    // Email Provider temporarily removed for build debugging
  ],
});

