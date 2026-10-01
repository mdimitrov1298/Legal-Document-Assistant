# Build stage: compile the static bundle.
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Optional absolute API base (e.g. http://127.0.0.1:8000/api/v1). Leave empty to
# use the same-origin /api/v1 path proxied by nginx below.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# Runtime stage: serve dist/ and proxy /api to the backend service.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
