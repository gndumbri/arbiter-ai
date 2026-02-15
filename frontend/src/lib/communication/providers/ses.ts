import { SESv2Client, SendEmailCommand } from "@aws-sdk/client-sesv2";
import { CommunicationProvider, EmailMessage } from "../types";

export class SESProvider implements CommunicationProvider {
  name = "SES";
  private client: SESv2Client;
  private sender: { email: string; name: string };

  constructor(region: string, sender: { email: string; name: string }) {
    this.client = new SESv2Client({ region });
    this.sender = sender;
  }

  async sendEmail(message: EmailMessage): Promise<string> {
    const command = new SendEmailCommand({
      FromEmailAddress: `${this.sender.name} <${this.sender.email}>`,
      Destination: {
        ToAddresses: message.to.map((r) => r.email),
      },
      Content: {
        Simple: {
          Subject: { Data: message.subject, Charset: "UTF-8" },
          Body: {
            ...(message.html
              ? { Html: { Data: message.html, Charset: "UTF-8" } }
              : {}),
            ...(message.text
              ? { Text: { Data: message.text, Charset: "UTF-8" } }
              : {}),
          },
        },
      },
      EmailTags: message.tags?.map((tag) => ({
        Name: "tag",
        Value: tag,
      })),
    });

    const result = await this.client.send(command);
    return result.MessageId ?? "unknown";
  }
}
