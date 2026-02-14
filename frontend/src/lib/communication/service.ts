import { BrevoProvider } from "./providers/brevo";
import { CommunicationProvider, EmailMessage } from "./types";

class CommunicationService {
  private transactionalProvider: CommunicationProvider;
  private marketingProvider: CommunicationProvider;

  constructor() {
    // We can configure different providers for different purposes here
    // For now, both use Brevo
    const apiKey = process.env.BREVO_API_KEY || "";
    const sender = {
        email: process.env.EMAIL_FROM || "noreply@arbiter-ai.com",
        name: process.env.EMAIL_FROM_NAME || "Arbiter AI",
    };

    const brevo = new BrevoProvider(apiKey, sender);
    
    this.transactionalProvider = brevo;
    this.marketingProvider = brevo;
  }

  async sendTransactionalEmail(message: EmailMessage): Promise<string> {
    return this.transactionalProvider.sendEmail(message);
  }

  async sendMarketingEmail(message: EmailMessage): Promise<string> {
    return this.marketingProvider.sendEmail(message);
  }
}

export const communication = new CommunicationService();
