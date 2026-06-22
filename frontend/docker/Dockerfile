# Frontend Dockerfile for FstvlPress
# Multi-stage build: Node for building, nginx for serving

# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --ignore-scripts

# Copy source code
COPY . .

# Build arguments for environment configuration
ARG VITE_API_BASE=/api/v1
ARG VITE_APP_DISPLAY_NAME=
ARG VITE_OIDC_URL=
ARG VITE_OIDC_REALM_NAME=
ARG VITE_OIDC_CLIENT_ID=

# Set environment variables for build
ENV VITE_API_BASE=${VITE_API_BASE} \
    VITE_APP_DISPLAY_NAME=${VITE_APP_DISPLAY_NAME} \
    VITE_OIDC_URL=${VITE_OIDC_URL} \
    VITE_OIDC_REALM_NAME=${VITE_OIDC_REALM_NAME} \
    VITE_OIDC_CLIENT_ID=${VITE_OIDC_CLIENT_ID}

# Build the application
RUN npm run build

# Production stage
FROM nginx:1.27-alpine AS production

# Install wget for healthcheck (not included in nginx:alpine by default)
RUN apk add --no-cache wget

# Copy nginx config template (S3_BUCKET substituted at runtime)
COPY docker/nginx.conf.template /etc/nginx/nginx.conf.template

# Copy entrypoint for runtime config generation
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Add non-root user
RUN adduser -D -u 1000 nginx-user && \
    mkdir -p /var/cache/nginx/public_api && \
    chown -R nginx-user:nginx-user /usr/share/nginx/html && \
    chown -R nginx-user:nginx-user /var/cache/nginx && \
    chown -R nginx-user:nginx-user /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx-user:nginx-user /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/health || exit 1

# Expose port
EXPOSE 80

# Run via entrypoint (substitutes S3_BUCKET into nginx config)
ENTRYPOINT ["/docker-entrypoint.sh"]
