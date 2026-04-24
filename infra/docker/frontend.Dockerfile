# AXON frontend — multi-stage build for Cloud Run.
FROM node:20-alpine AS deps
WORKDIR /app
COPY pnpm-workspace.yaml package.json ./
COPY shared/package.json ./shared/
COPY frontend/package.json ./frontend/
RUN corepack enable && pnpm install --frozen-lockfile

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/frontend/node_modules ./frontend/node_modules
COPY shared ./shared
COPY frontend ./frontend
RUN corepack enable && pnpm --filter @axon/frontend build

FROM nginx:alpine AS runtime
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
