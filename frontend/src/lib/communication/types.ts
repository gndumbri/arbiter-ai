export interface EmailMessage {
  to: { email: string; name?: string }[];
  subject: string;
  html?: string;
  text?: string;
  templateId?: number;
  params?: Record<string, unknown>;
  tags?: string[];
}

export interface SMSMessage {
  to: string;
  content: string;
}

export interface CommunicationProvider {
  name: string;
  sendEmail(message: EmailMessage): Promise<string>; // Returns ID
  // sendSMS(message: SMSMessage): Promise<string>; // Future
}
