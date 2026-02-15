import NextAuth from "next-auth";
// import { DrizzleAdapter } from "@auth/drizzle-adapter";
// import { db } from "@/db";
// import { accounts, users, verificationTokens } from "@/db/auth-schema";
import Email from "next-auth/providers/email";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";
import { communication } from "@/lib/communication/service";

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
    // Email({
    //   server: process.env.EMAIL_SERVER, // Optional if using custom sendVerificationRequest
    //   from: process.env.EMAIL_FROM,
    //   sendVerificationRequest: async (params) => {
    //     const { identifier: to, url, provider, theme } = params;
    //     const { host } = new URL(url);
        
    //     // Use our new Communication Service (Brevo)
    //     await communication.sendTransactionalEmail({
    //         to: [{ email: to }],
    //         subject: `Sign in to ${host}`,
    //         text: text({ url, host }),
    //         html: html({ url, host, theme }),
    //     });
    //   },
    // }),
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
             return { id: "dev-user-id", email: email, name: "Kasey Kaplan (Dev)" };
        }
        return null;
      }
    })
  ],
});

/**
 * Email HTML body
 * Insert invisible space into domains from being turned into a hyperlink by email
 * clients like Outlook and Apple mail, as this is confusing because it seems
 * like they are supposed to click on it to sign in.
 *
 * @note We are not using a template yet, but we could switch to Brevo templates later.
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
