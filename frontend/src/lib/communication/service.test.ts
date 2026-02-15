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
      brevoApiKey: "key-present",
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
      brevoApiKey: "key-present",
      transactionalProvider: primary,
      fallbackProvider: fallback,
    });

    await expect(service.sendTransactionalEmail(sampleEmail)).rejects.toThrow(
      "provider down"
    );
    expect(fallbackSend).not.toHaveBeenCalled();
  });

  it("throws in production when Brevo key is missing", async () => {
    const service = new CommunicationService({
      appMode: "production",
      brevoApiKey: "",
    });

    await expect(service.sendTransactionalEmail(sampleEmail)).rejects.toThrow(
      "BREVO_API_KEY is required in production email flows."
    );
  });

  it("uses primary provider when send succeeds", async () => {
    const primarySend = vi.fn().mockResolvedValue("primary-id");
    const primary = new StubProvider(primarySend);

    const service = new CommunicationService({
      appMode: "sandbox",
      brevoApiKey: "key-present",
      transactionalProvider: primary,
    });

    const id = await service.sendTransactionalEmail(sampleEmail);

    expect(id).toBe("primary-id");
    expect(primarySend).toHaveBeenCalledTimes(1);
  });
});
