import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-auth/react", () => ({
  getSession: vi.fn(),
}));

import { getSession } from "next-auth/react";
import { fetcher } from "./api";

describe("fetcher", () => {
  beforeEach(() => {
    vi.mocked(getSession).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it.each([204, 205])("returns undefined for %i no-content responses", async (statusCode) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: statusCode }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetcher<void>("/library/entry-id", { method: "DELETE" });

    expect(result).toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns undefined for successful empty response bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetcher<void>("/library");

    expect(result).toBeUndefined();
  });

  it("parses JSON response bodies when present", async () => {
    const payload = { ok: true, id: "123" };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetcher<{ ok: boolean; id: string }>("/sessions");

    expect(result).toEqual(payload);
  });

  it("throws backend detail message on error responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetcher("/judge", { method: "POST" })).rejects.toThrow("Bad request");
  });
});
