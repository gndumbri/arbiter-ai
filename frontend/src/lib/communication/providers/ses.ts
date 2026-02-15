import nodemailer from "nodemailer";

import { CommunicationProvider, EmailMessage } from "../types";

type SesProviderOptions = {
  sender: { email: string; name?: string };
  smtpUrl?: string;
  host?: string;
  port?: number;
  secure?: boolean;
  username?: string;
  password?: string;
};

export class SesProvider implements CommunicationProvider {
  name = "SES";
  private sender: { email: string; name?: string };
  private transporter: nodemailer.Transporter | null;

  constructor(options: SesProviderOptions) {
    this.sender = options.sender;
    this.transporter = this.createTransporter(options);
  }

  isConfigured(): boolean {
    return this.transporter !== null;
  }

  async sendEmail(message: EmailMessage): Promise<string> {
    if (!this.transporter) {
      throw new Error(
        "SES provider is not configured. Set EMAIL_SERVER or SES_SMTP_HOST/SES_SMTP_USER/SES_SMTP_PASS."
      );
    }

    const result = await this.transporter.sendMail({
      from: this.formatSender(),
      to: message.to.map((entry) => (entry.name ? `${entry.name} <${entry.email}>` : entry.email)),
      subject: message.subject,
      html: message.html,
      text: message.text,
    });

    return result.messageId || `ses-${Date.now()}`;
  }

  private createTransporter(options: SesProviderOptions): nodemailer.Transporter | null {
    const smtpUrl = (options.smtpUrl || "").trim();
    if (smtpUrl) {
      return nodemailer.createTransport(smtpUrl);
    }

    const host = (options.host || "").trim();
    const username = (options.username || "").trim();
    const password = (options.password || "").trim();
    if (!host || !username || !password) {
      return null;
    }

    const port = options.port ?? 587;
    return nodemailer.createTransport({
      host,
      port,
      secure: options.secure ?? port === 465,
      auth: {
        user: username,
        pass: password,
      },
    });
  }

  private formatSender(): string {
    if (this.sender.name) {
      return `${this.sender.name} <${this.sender.email}>`;
    }
    return this.sender.email;
  }
}
