import { ConsoleEmailProvider } from "./providers/console";
import { BrevoProvider } from "./providers/brevo";
import { CommunicationProvider, EmailMessage } from "./types";

type AppMode = "mock" | "sandbox" | "production";

function resolveAppMode(value: string | undefined): AppMode {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "production") return "production";
  if (normalized === "mock") return "mock";
  return "sandbox";
}

type CommunicationServiceOptions = {
  appMode?: string;
  brevoApiKey?: string;
  sender?: { email: string; name: string };
  transactionalProvider?: CommunicationProvider;
  marketingProvider?: CommunicationProvider;
  fallbackProvider?: CommunicationProvider;
};

export class CommunicationService {
  private appMode: AppMode;
  private transactionalProvider: CommunicationProvider;
  private marketingProvider: CommunicationProvider;
  private fallbackProvider: CommunicationProvider;
  private hasBrevoKey: boolean;

  constructor(options: CommunicationServiceOptions = {}) {
    this.appMode = resolveAppMode(options.appMode ?? process.env.APP_MODE);
    const brevoApiKey = options.brevoApiKey ?? (process.env.BREVO_API_KEY || "");
    const sender = options.sender || {
      email: process.env.EMAIL_FROM || "noreply@arbiter-ai.com",
      name: process.env.EMAIL_FROM_NAME || "Arbiter AI",
    };

    const brevo = new BrevoProvider(brevoApiKey, sender);
    const fallback = options.fallbackProvider || new ConsoleEmailProvider();
    this.hasBrevoKey = Boolean(brevoApiKey.trim());
    this.fallbackProvider = fallback;

    // Override hooks used by tests.
    if (options.transactionalProvider) {
      this.transactionalProvider = options.transactionalProvider;
    } else {
      this.transactionalProvider = this.hasBrevoKey ? brevo : fallback;
    }
    if (options.marketingProvider) {
      this.marketingProvider = options.marketingProvider;
    } else {
      this.marketingProvider = this.hasBrevoKey ? brevo : fallback;
    }

    if (!this.hasBrevoKey && this.appMode !== "production") {
      console.warn("BREVO_API_KEY not set. Using console email fallback in non-production mode.");
    }
  }

  private async sendWithFallback(
    provider: CommunicationProvider,
    message: EmailMessage,
    channel: "transactional" | "marketing"
  ): Promise<string> {
    if (this.appMode === "production" && !this.hasBrevoKey) {
      throw new Error("BREVO_API_KEY is required in production email flows.");
    }

    try {
      return await provider.sendEmail(message);
    } catch (error) {
      if (this.appMode === "production") {
        throw error;
      }
      const messageText = error instanceof Error ? error.message : String(error);
      console.warn(
        `${channel} email provider failed in ${this.appMode}. Falling back to console provider.`,
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
