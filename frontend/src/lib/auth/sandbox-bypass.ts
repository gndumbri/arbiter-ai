export type SandboxBypassUser = {
  id: string;
  email: string;
  name: string;
};

const DISABLED_TOKENS = new Set(["0", "false", "no", "off"]);

// WHY: Stable IDs keep user records consistent across sandbox restarts.
const SANDBOX_BYPASS_USERS: Record<string, { id: string; name: string }> = {
  "kasey.kaplan@gmail.com": {
    id: "f6f4aede-0673-49ab-8c63-cf569273c267",
    name: "Kasey Kaplan (Sandbox)",
  },
  "gndumbri@gmail.com": {
    id: "25e3a23b-2a11-4529-8323-4acdb5b5be30",
    name: "Gndumbri (Sandbox)",
  },
};

export function normalizeEmail(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

export function shouldAttemptSandboxBypassFromClient(email: string): boolean {
  const normalized = normalizeEmail(email);
  return Object.prototype.hasOwnProperty.call(SANDBOX_BYPASS_USERS, normalized);
}

export function isSandboxBypassEnabled(
  appMode: string | undefined,
  enabledFlag: string | undefined
): boolean {
  if ((appMode || "").trim().toLowerCase() !== "sandbox") {
    return false;
  }
  const normalizedFlag = (enabledFlag || "true").trim().toLowerCase();
  return !DISABLED_TOKENS.has(normalizedFlag);
}

export function getSandboxBypassUser(
  email: string | null | undefined,
  appMode: string | undefined,
  enabledFlag: string | undefined
): SandboxBypassUser | null {
  if (!isSandboxBypassEnabled(appMode, enabledFlag)) {
    return null;
  }

  const normalized = normalizeEmail(email);
  const sandboxUser = SANDBOX_BYPASS_USERS[normalized];
  if (!sandboxUser) return null;

  return {
    id: sandboxUser.id,
    email: normalized,
    name: sandboxUser.name,
  };
}
