import NextAuth from "next-auth";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { getDb } from "@/db";
import { accounts, users, verificationTokens } from "@/db/auth-schema";
import { createHmac } from "crypto";
import Email from "next-auth/providers/email";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";
import { communication } from "@/lib/communication/service";

function base64UrlEncode(value: string): string {
  return Buffer.from(value).toString("base64url");
}

function createBackendAccessToken(payload: {
  sub: string;
  email?: string | null;
  name?: string | null;
}): string | null {
  const secret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET;
  if (!secret || !payload.sub) return null;

  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "HS256", typ: "JWT" };
  const claims = {
    sub: payload.sub,
    email: payload.email ?? undefined,
    name: payload.name ?? undefined,
    iat: now,
    exp: now + 60 * 60, // 1 hour
  };

  const encodedHeader = base64UrlEncode(JSON.stringify(header));
  const encodedClaims = base64UrlEncode(JSON.stringify(claims));
  const signingInput = `${encodedHeader}.${encodedClaims}`;
  const signature = createHmac("sha256", secret).update(signingInput).digest("base64url");
  return `${signingInput}.${signature}`;
}

// WHY: Build the adapter only when DATABASE_URL is available. During `next build`
// in Docker there is no database, so we skip the adapter to avoid a build-time crash.
const adapter = process.env.DATABASE_URL
  ? DrizzleAdapter(getDb(), {
      usersTable: users,
      accountsTable: accounts,
      verificationTokensTable: verificationTokens,
    })
  : undefined;

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  ...(adapter ? { adapter } : {}),
  session: { strategy: "jwt" },
  callbacks: {
    ...authConfig.callbacks,
    jwt({ token, user }) {
      if (user) {
        token.sub = user.id;
        token.email = user.email;
        token.name = user.name;
      }
      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub;
        const accessToken = createBackendAccessToken({
          sub: token.sub,
          email: token.email,
          name: token.name,
        });
        if (accessToken) {
          (session as { accessToken?: string }).accessToken = accessToken;
        }
      }
      return session;
    },
  },
  providers: [
    Email({
      // Placeholder is required by provider validation when we use a custom sender.
      server: process.env.EMAIL_SERVER || "smtp://localhost:25",
      from: process.env.EMAIL_FROM || "noreply@arbiter-ai.com",
      sendVerificationRequest: async (params) => {
        const { identifier: to, url, theme } = params;
        const signInHost = new URL(url).host;

        await communication.sendTransactionalEmail({
          to: [{ email: to }],
          subject: `Sign in to ${signInHost}`,
          text: text({ url, host: signInHost }),
          html: html({ url, host: signInHost, theme }),
        });
      },
    }),
    Credentials({
      id: "credentials",
      name: "Dev Login",
      credentials: {
        email: { label: "Email", type: "email" },
      },
      authorize: async (credentials) => {
        if (process.env.NODE_ENV !== "development") return null;

        const email = credentials.email as string;
        // Allow specific dev emails or just checking format
        if (email === "kasey.kaplan@gmail.com") {
          return {
            id: "f6f4aede-0673-49ab-8c63-cf569273c267",
            email,
            name: "Kasey Kaplan (Dev)",
          };
        }
        return null;
      },
    }),
  ],
});

/**
 * Email HTML body
 * Insert invisible space into domains from being turned into a hyperlink by email
 * clients like Outlook and Apple mail, as this is confusing because it seems
 * like they are supposed to click on it to sign in.
 *
 * @note We are not using a template yet, but we could switch to SES templates later.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function html(params: { url: string; host: string; theme: any }) {
  const { url, host, theme } = params;

  const escapedHost = host.replace(/\./g, "&#8203;.");

  const brandColor = theme.brandColor || "#346df1";
  const color = {
    background: "#f9f9f9",
    text: "#444",
    mainBackground: "#fff",
    buttonBackground: brandColor,
    buttonBorder: brandColor,
    buttonText: theme.buttonText || "#fff",
  };

  return `
<body style="background: ${color.background};">
  <table width="100%" border="0" cellspacing="20" cellpadding="0"
    style="background: ${color.background}; max-width: 600px; margin: auto; border-radius: 10px;">
    <tr>
      <td align="center"
        style="padding: 10px 0px; font-size: 22px; font-family: Helvetica, Arial, sans-serif; color: ${color.text};">
        Sign in to <strong>${escapedHost}</strong>
      </td>
    </tr>
    <tr>
      <td align="center" style="padding: 20px 0;">
        <table border="0" cellspacing="0" cellpadding="0">
          <tr>
            <td align="center" style="border-radius: 5px;" bgcolor="${color.buttonBackground}"><a href="${url}"
                target="_blank"
                style="font-size: 18px; font-family: Helvetica, Arial, sans-serif; color: ${color.buttonText}; text-decoration: none; border-radius: 5px; padding: 10px 20px; border: 1px solid ${color.buttonBorder}; display: inline-block; font-weight: bold;">Sign
                in</a></td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td align="center"
        style="padding: 0px 0px 10px 0px; font-size: 16px; line-height: 22px; font-family: Helvetica, Arial, sans-serif; color: ${color.text};">
        If you did not request this email you can safely ignore it.
      </td>
    </tr>
  </table>
</body>
`;
}

/** Email Text body (fallback for email clients that don't render HTML) */
function text({ url, host }: { url: string; host: string }) {
  return `Sign in to ${host}\n${url}\n\n`;
}
