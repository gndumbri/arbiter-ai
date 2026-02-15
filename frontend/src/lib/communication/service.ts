import { ConsoleEmailProvider } from "./providers/console";
import { BrevoProvider } from "./providers/brevo";
import { SesProvider } from "./providers/ses";
import { CommunicationProvider, EmailMessage } from "./types";

type AppMode = "mock" | "sandbox" | "production";
type EmailProviderName = "ses" | "brevo" | "console";

function resolveAppMode(value: string | undefined): AppMode {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "production") return "production";
  if (normalized === "mock") return "mock";
  return "sandbox";
}

function resolveEmailProvider(value: string | undefined): EmailProviderName {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "brevo") return "brevo";
  if (normalized === "console") return "console";
  return "ses";
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (!value) return fallback;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return fallback;
}

function parsePort(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

type CommunicationServiceOptions = {
  appMode?: string;
  emailProvider?: string;
  emailServer?: string;
  brevoApiKey?: string;
  sesSmtpHost?: string;
  sesSmtpPort?: number;
  sesSmtpSecure?: boolean;
  sesSmtpUser?: string;
  sesSmtpPass?: string;
  awsRegion?: string;
  providerConfigured?: boolean;
  providerConfigError?: string;
  sender?: { email: string; name: string };
  transactionalProvider?: CommunicationProvider;
  marketingProvider?: CommunicationProvider;
  fallbackProvider?: CommunicationProvider;
};

export class CommunicationService {
  private appMode: AppMode;
  private emailProvider: EmailProviderName;
  private transactionalProvider: CommunicationProvider;
  private marketingProvider: CommunicationProvider;
  private fallbackProvider: CommunicationProvider;
  private providerConfigured: boolean;
  private providerConfigError: string;

  constructor(options: CommunicationServiceOptions = {}) {
    this.appMode = resolveAppMode(options.appMode ?? process.env.APP_MODE);
    this.emailProvider = resolveEmailProvider(options.emailProvider ?? process.env.EMAIL_PROVIDER);

    const brevoApiKey = (options.brevoApiKey ?? process.env.BREVO_API_KEY ?? "").trim();
    const emailServer = (options.emailServer ?? process.env.EMAIL_SERVER ?? "").trim();
    const awsRegion = (options.awsRegion ?? process.env.AWS_REGION ?? "us-east-1").trim();
    const sesHost = (
      options.sesSmtpHost ??
      process.env.SES_SMTP_HOST ??
      (awsRegion ? `email-smtp.${awsRegion}.amazonaws.com` : "")
    ).trim();
    const sesPort = options.sesSmtpPort ?? parsePort(process.env.SES_SMTP_PORT, 587);
    const sesSecure = options.sesSmtpSecure ?? parseBoolean(process.env.SES_SMTP_SECURE, sesPort === 465);
    const sesUser = (
      options.sesSmtpUser ??
      process.env.SES_SMTP_USER ??
      process.env.SES_SMTP_USERNAME ??
      process.env.SMTP_USERNAME ??
      ""
    ).trim();
    const sesPass = (
      options.sesSmtpPass ??
      process.env.SES_SMTP_PASS ??
      process.env.SES_SMTP_PASSWORD ??
      process.env.SMTP_PASSWORD ??
      ""
    ).trim();

    const sender = options.sender || {
      email: process.env.EMAIL_FROM || "noreply@arbiter-ai.com",
      name: process.env.EMAIL_FROM_NAME || "Arbiter AI",
    };

    const fallback = options.fallbackProvider || new ConsoleEmailProvider();
    this.fallbackProvider = fallback;
    const brevo = new BrevoProvider(brevoApiKey, sender);
    const ses = new SesProvider({
      sender,
      smtpUrl: emailServer,
      host: sesHost,
      port: sesPort,
      secure: sesSecure,
      username: sesUser,
      password: sesPass,
    });

    let provider: CommunicationProvider = fallback;
    let configured = true;
    let configError = "";

    if (this.emailProvider === "brevo") {
      configured = Boolean(brevoApiKey);
      provider = configured ? brevo : fallback;
      configError =
        "EMAIL_PROVIDER=brevo requires BREVO_API_KEY in production email flows.";
    } else if (this.emailProvider === "ses") {
      configured = ses.isConfigured();
      provider = configured ? ses : fallback;
      configError =
        "EMAIL_PROVIDER=ses requires EMAIL_SERVER or SES_SMTP_HOST/SES_SMTP_USER/SES_SMTP_PASS in production email flows.";
    } else {
      configured = true;
      provider = fallback;
      configError = "";
    }

    const hasProviderOverrides = Boolean(options.transactionalProvider || options.marketingProvider);
    this.providerConfigured = options.providerConfigured ?? (hasProviderOverrides ? true : configured);
    this.providerConfigError =
      options.providerConfigError ??
      (this.providerConfigured ? "" : configError || "Email provider is not configured.");

    if (options.transactionalProvider) {
      this.transactionalProvider = options.transactionalProvider;
    } else {
      this.transactionalProvider = provider;
    }
    if (options.marketingProvider) {
      this.marketingProvider = options.marketingProvider;
    } else {
      this.marketingProvider = provider;
    }

    if (!this.providerConfigured && this.appMode !== "production") {
      console.warn(
        `${this.providerConfigError} Using console email fallback in ${this.appMode} mode.`
      );
    }
  }

  private async sendWithFallback(
    provider: CommunicationProvider,
    message: EmailMessage,
    channel: "transactional" | "marketing"
  ): Promise<string> {
    if (this.appMode === "production" && !this.providerConfigured) {
      throw new Error(this.providerConfigError);
    }

    try {
      return await provider.sendEmail(message);
    } catch (error) {
      if (this.appMode === "production") {
        throw error;
      }
      const messageText = error instanceof Error ? error.message : String(error);
      console.warn(
        `${channel} email provider (${this.emailProvider}) failed in ${this.appMode}. Falling back to console provider.`,
        messageText
      );
      return this.fallbackProvider.sendEmail(message);
    }
  }

  async sendTransactionalEmail(message: EmailMessage): Promise<string> {
    return this.sendWithFallback(this.transactionalProvider, message, "transactional");
  }

  async sendMarketingEmail(message: EmailMessage): Promise<string> {
    return this.sendWithFallback(this.marketingProvider, message, "marketing");
  }
}

export const communication = new CommunicationService();
