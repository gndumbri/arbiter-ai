# ── Stage 1: Install dependencies ─────────────────────────────────────────────
FROM node:25-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* .npmrc ./
# WHY: .npmrc sets legacy-peer-deps=true, so npm ci respects it
# without needing a CLI flag. npm ci gives deterministic builds from the lockfile.
RUN npm ci

# ── Stage 2: Build ───────────────────────────────────────────────────────────
FROM node:25-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# WHY: Next.js needs these at BUILD time for static optimization.
# Runtime secrets are injected via environment variables at container start.
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: Runtime ─────────────────────────────────────────────────────────
FROM node:25-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# WHY: Run as non-root for security (principle of least privilege)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only the build output and necessary files
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
