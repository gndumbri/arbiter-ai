import { CommunicationProvider, EmailMessage } from "../types";

export class ConsoleEmailProvider implements CommunicationProvider {
  name = "ConsoleEmail";

  async sendEmail(message: EmailMessage): Promise<string> {
    console.warn("Email provider fallback active. Logging message instead of sending.");
    console.log("Email:", JSON.stringify(message, null, 2));
    return `console-${Date.now()}`;
  }
}
