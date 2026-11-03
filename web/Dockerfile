FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci when a lockfile exists (reproducible); npm install as the fallback so
# a fresh clone without one still builds.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi


FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


FROM node:20-alpine AS runtime
WORKDIR /app
# BACKEND_URL is read at request time by next.config.mjs's rewrite, so the
# same image runs against any backend without a rebuild.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 \
    BACKEND_URL=http://api:8000

RUN addgroup -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs

# Next's standalone output ships only the files the server actually needs.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
