# The web app (Next.js). Build from the repo root:  docker build -f infra/docker/web.Dockerfile .
FROM node:22-slim
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
# the browser calls the API directly, so its address is fixed when the pages are built
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
