# AXON backend (NestJS) — Cloud Run.
FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY shared ./shared
COPY backend ./backend
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @axon/backend build
RUN pnpm deploy --filter=@axon/backend --prod /prod/backend

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production BACKEND_PORT=8080
COPY --from=builder /prod/backend ./
EXPOSE 8080
CMD ["node", "dist/main.js"]
