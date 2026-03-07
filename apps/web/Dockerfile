FROM node:22-alpine AS builder

WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/types/package.json packages/types/package.json
COPY packages/ui/package.json packages/ui/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages packages

ARG VITE_KEYCLOAK_URL=http://localhost:8080
ARG VITE_KEYCLOAK_REALM=qaongdur-dev
ARG VITE_KEYCLOAK_CLIENT_ID=qaongdur-web
ARG VITE_KEYCLOAK_STEP_UP_ACR=urn:qaongdur:loa:2
ARG VITE_CONTROL_API_BASE_URL=http://localhost:8000

ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}
ENV VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM}
ENV VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}
ENV VITE_KEYCLOAK_STEP_UP_ACR=${VITE_KEYCLOAK_STEP_UP_ACR}
ENV VITE_CONTROL_API_BASE_URL=${VITE_CONTROL_API_BASE_URL}

RUN pnpm --filter @qaongdur/web build

FROM node:22-alpine AS runtime

WORKDIR /app

RUN npm install -g serve@14.2.4

COPY --from=builder /workspace/apps/web/dist ./dist

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173"]
