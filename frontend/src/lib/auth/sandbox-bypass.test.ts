import { describe, expect, it } from "vitest";

import {
  getSandboxBypassUser,
  isSandboxBypassEnabled,
  normalizeEmail,
  shouldAttemptSandboxBypassFromClient,
} from "./sandbox-bypass";

describe("sandbox email bypass policy", () => {
  it("normalizes emails for comparisons", () => {
    expect(normalizeEmail("  Kasey.Kaplan@gmail.com ")).toBe("kasey.kaplan@gmail.com");
  });

  it("enables bypass only in sandbox mode by default", () => {
    expect(isSandboxBypassEnabled("sandbox", undefined)).toBe(true);
    expect(isSandboxBypassEnabled("production", undefined)).toBe(false);
  });

  it("can be disabled via env flag", () => {
    expect(isSandboxBypassEnabled("sandbox", "false")).toBe(false);
    expect(isSandboxBypassEnabled("sandbox", "0")).toBe(false);
  });

  it("returns bypass users only for allowlisted emails in sandbox", () => {
    const kasey = getSandboxBypassUser("kasey.kaplan@gmail.com", "sandbox", "true");
    const gndumbri = getSandboxBypassUser("gndumbri@gmail.com", "sandbox", "true");
    const denied = getSandboxBypassUser("someone@example.com", "sandbox", "true");

    expect(kasey?.email).toBe("kasey.kaplan@gmail.com");
    expect(gndumbri?.email).toBe("gndumbri@gmail.com");
    expect(denied).toBeNull();
  });

  it("client should only attempt bypass for allowlisted emails", () => {
    expect(shouldAttemptSandboxBypassFromClient("kasey.kaplan@gmail.com")).toBe(true);
    expect(shouldAttemptSandboxBypassFromClient("gndumbri@gmail.com")).toBe(true);
    expect(shouldAttemptSandboxBypassFromClient("other@example.com")).toBe(false);
  });
});
