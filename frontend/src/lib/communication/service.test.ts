import { describe, expect, it, vi } from "vitest";

import { CommunicationProvider, EmailMessage } from "./types";
import { CommunicationService } from "./service";

class StubProvider implements CommunicationProvider {
  name = "Stub";
  constructor(private behavior: (message: EmailMessage) => Promise<string>) {}
  async sendEmail(message: EmailMessage): Promise<string> {
    return this.behavior(message);
  }
}

const sampleEmail: EmailMessage = {
  to: [{ email: "player@example.com" }],
  subject: "Test",
  text: "Hello",
};

describe("CommunicationService", () => {
  it("falls back in sandbox when transactional provider fails", async () => {
    const primary = new StubProvider(async () => {
      throw new Error("provider down");
    });
    const fallbackSend = vi.fn().mockResolvedValue("fallback-id");
    const fallback = new StubProvider(fallbackSend);

    const service = new CommunicationService({
      appMode: "sandbox",
      emailProvider: "ses",
      transactionalProvider: primary,
      fallbackProvider: fallback,
    });

    const id = await service.sendTransactionalEmail(sampleEmail);

    expect(id).toBe("fallback-id");
    expect(fallbackSend).toHaveBeenCalledTimes(1);
  });

  it("throws in production when transactional provider fails", async () => {
    const primary = new StubProvider(async () => {
      throw new Error("provider down");
    });
    const fallbackSend = vi.fn().mockResolvedValue("fallback-id");
    const fallback = new StubProvider(fallbackSend);

    const service = new CommunicationService({
      appMode: "production",
      emailProvider: "ses",
      transactionalProvider: primary,
      fallbackProvider: fallback,
    });

    await expect(service.sendTransactionalEmail(sampleEmail)).rejects.toThrow(
      "provider down"
    );
    expect(fallbackSend).not.toHaveBeenCalled();
  });

  it("throws in production when SES config is missing", async () => {
    const service = new CommunicationService({
      appMode: "production",
      emailProvider: "ses",
      emailServer: "",
      sesSmtpHost: "",
      sesSmtpUser: "",
      sesSmtpPass: "",
    });

    await expect(service.sendTransactionalEmail(sampleEmail)).rejects.toThrow(
      "EMAIL_PROVIDER=ses requires EMAIL_SERVER or SES_SMTP_HOST/SES_SMTP_USER/SES_SMTP_PASS in production email flows."
    );
  });

  it("throws in production when Brevo config is selected but key is missing", async () => {
    const service = new CommunicationService({
      appMode: "production",
      emailProvider: "brevo",
      brevoApiKey: "",
    });

    await expect(service.sendTransactionalEmail(sampleEmail)).rejects.toThrow(
      "EMAIL_PROVIDER=brevo requires BREVO_API_KEY in production email flows."
    );
  });

  it("uses primary provider when send succeeds", async () => {
    const primarySend = vi.fn().mockResolvedValue("primary-id");
    const primary = new StubProvider(primarySend);

    const service = new CommunicationService({
      appMode: "sandbox",
      emailProvider: "ses",
      transactionalProvider: primary,
    });

    const id = await service.sendTransactionalEmail(sampleEmail);

    expect(id).toBe("primary-id");
    expect(primarySend).toHaveBeenCalledTimes(1);
  });

  it("allows console provider in production for explicit emergency fallback mode", async () => {
    const service = new CommunicationService({
      appMode: "production",
      emailProvider: "console",
    });

    const id = await service.sendTransactionalEmail(sampleEmail);
    expect(id.startsWith("console-")).toBe(true);
  });
});
