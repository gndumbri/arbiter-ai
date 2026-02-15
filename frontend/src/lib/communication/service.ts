import { ConsoleEmailProvider } from "./providers/console";
import { SESProvider } from "./providers/ses";
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
  awsRegion?: string;
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

  constructor(options: CommunicationServiceOptions = {}) {
    this.appMode = resolveAppMode(options.appMode ?? process.env.APP_MODE);
    const awsRegion = options.awsRegion ?? process.env.AWS_REGION ?? "us-east-1";
    const sender = options.sender || {
      email: process.env.EMAIL_FROM || "noreply@arbiter-ai.com",
      name: process.env.EMAIL_FROM_NAME || "Arbiter AI",
    };

    const ses = new SESProvider(awsRegion, sender);
    const fallback = options.fallbackProvider || new ConsoleEmailProvider();
    this.fallbackProvider = fallback;

    // In production and sandbox, use SES (IAM credentials are provided by the
    // ECS task role). In mock mode, always use the console fallback.
    const useSES = this.appMode !== "mock";

    if (options.transactionalProvider) {
      this.transactionalProvider = options.transactionalProvider;
    } else {
      this.transactionalProvider = useSES ? ses : fallback;
    }
    if (options.marketingProvider) {
      this.marketingProvider = options.marketingProvider;
    } else {
      this.marketingProvider = useSES ? ses : fallback;
    }

    if (!useSES) {
      console.warn("APP_MODE=mock. Using console email fallback.");
    }
  }

  private async sendWithFallback(
    provider: CommunicationProvider,
    message: EmailMessage,
    channel: "transactional" | "marketing"
  ): Promise<string> {
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
