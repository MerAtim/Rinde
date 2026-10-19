# syntax=docker/dockerfile:1

# Imágenes fijadas por digest: siempre se construye con exactamente los mismos bytes.

# Etapa 1: compila la aplicación.
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

# Etapa 2: nginx sin privilegios sirve solo los archivos estáticos compilados.
FROM nginxinc/nginx-unprivileged:1-alpine@sha256:b54ac358b83fc6c965793fd271839b4ea4cdb6e99895bb19618cbc2ca152d972 AS runtime
fix/cve-2026-93990-expat

# Security fix: ensure expat (libexpat) is upgraded to the patched version that fixes CVE-2026-93990.
# Use apk to refresh indexes and upgrade/install the package in the final runtime layer.
RUN apk update && apk add --no-cache -U expat


# Aplica los parches de seguridad publicados después de la imagen base (igual que el backend).
# La imagen corre como el usuario sin privilegios 101: se instala como root y se vuelve a él.
USER root
RUN apk upgrade --no-cache
USER 101
main
ENV API_UPSTREAM=http://api:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
