import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

// WHY: Lazy initialization so that importing this module during `next build`
// (when DATABASE_URL is not available) doesn't throw at module-load time.
let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;

export function getDb() {
  if (!_db) {
    let connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error("Missing DATABASE_URL");
    }
    // WHY: The shared DATABASE_URL uses the +asyncpg driver suffix for the
    // Python/SQLAlchemy backend. postgres.js doesn't understand that scheme.
    connectionString = connectionString.replace(
      "postgresql+asyncpg://",
      "postgresql://",
    );
    const client = postgres(connectionString, {
      // WHY: RDS enforces SSL (rds.force_ssl=1 on PostgreSQL 16+). postgres.js
      // defaults to no SSL, unlike Python's asyncpg which defaults to ssl=prefer.
      // Skip SSL locally where Docker Compose Postgres has no certs.
      ssl: process.env.NODE_ENV === "production" ? "require" : false,
    });
    _db = drizzle(client, { schema });
  }
  return _db;
}
