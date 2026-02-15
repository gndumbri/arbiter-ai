import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next-auth/react", () => ({
  getSession: vi.fn(),
}));

const ORIGINAL_NODE_ENV = process.env.NODE_ENV;
const ORIGINAL_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL;

async function loadApiBaseUrl({
  nodeEnv,
  publicApiUrl,
}: {
  nodeEnv?: string;
  publicApiUrl?: string;
}): Promise<string> {
  if (nodeEnv === undefined) {
    delete process.env.NODE_ENV;
  } else {
    process.env.NODE_ENV = nodeEnv;
  }

  if (publicApiUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = publicApiUrl;
  }

  vi.resetModules();
  const mod = await import("./api");
  return mod.API_BASE_URL;
}

afterEach(() => {
  if (ORIGINAL_NODE_ENV === undefined) {
    delete process.env.NODE_ENV;
  } else {
    process.env.NODE_ENV = ORIGINAL_NODE_ENV;
  }

  if (ORIGINAL_PUBLIC_API_URL === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = ORIGINAL_PUBLIC_API_URL;
  }

  vi.resetModules();
});

describe("API base URL resolution", () => {
  it("uses same-origin /api/v1 fallback in production when NEXT_PUBLIC_API_URL is missing", async () => {
    const base = await loadApiBaseUrl({ nodeEnv: "production" });
    expect(base).toBe("/api/v1");
  });

  it("uses localhost fallback in development when NEXT_PUBLIC_API_URL is missing", async () => {
    const base = await loadApiBaseUrl({ nodeEnv: "development" });
    expect(base).toBe("http://localhost:8000/api/v1");
  });

  it("normalizes explicit NEXT_PUBLIC_API_URL without /api/v1 suffix", async () => {
    const base = await loadApiBaseUrl({
      nodeEnv: "production",
      publicApiUrl: "https://sandbox.arbiter-ai.com",
    });
    expect(base).toBe("https://sandbox.arbiter-ai.com/api/v1");
  });

  it("normalizes explicit NEXT_PUBLIC_API_URL with trailing slash", async () => {
    const base = await loadApiBaseUrl({
      nodeEnv: "production",
      publicApiUrl: "https://sandbox.arbiter-ai.com/api/v1/",
    });
    expect(base).toBe("https://sandbox.arbiter-ai.com/api/v1");
  });
});
