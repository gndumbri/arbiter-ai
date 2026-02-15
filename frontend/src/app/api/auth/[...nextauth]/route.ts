import { handlers } from "@/auth";

// WHY: Prevents Next.js from pre-rendering this route during `next build`.
// The auth handler requires DATABASE_URL which is only available at runtime.
export const dynamic = "force-dynamic";

export const { GET, POST } = handlers;
