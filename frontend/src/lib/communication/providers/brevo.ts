import { CommunicationProvider, EmailMessage } from "../types";

export class BrevoProvider implements CommunicationProvider {
  name = "Brevo";
  private apiKey: string;
  private sender: { email: string; name: string };

  constructor(apiKey: string, sender: { email: string; name: string }) {
    this.apiKey = apiKey;
    this.sender = sender;
  }

  async sendEmail(message: EmailMessage): Promise<string> {
    if (!this.apiKey) {
      throw new Error("Brevo API key is missing.");
    }

    const payload = {
      sender: this.sender,
      to: message.to,
      subject: message.subject,
      htmlContent: message.html,
      textContent: message.text,
      templateId: message.templateId,
      params: message.params,
      tags: message.tags,
    };

    const res = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: {
        "api-key": this.apiKey,
        "content-type": "application/json",
        accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(`Brevo Error: ${JSON.stringify(error)}`);
    }

    const data = await res.json();
    return data.messageId || `brevo-${Date.now()}`;
  }
}
