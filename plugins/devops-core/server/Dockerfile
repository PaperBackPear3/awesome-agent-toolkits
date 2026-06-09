FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
# Source is mounted at runtime via docker-compose volumes
CMD ["npx", "tsx", "watch", "server.ts"]

FROM node:22-alpine AS prod
WORKDIR /app
COPY bundle.mjs ./
COPY dist/ ./dist/
CMD ["node", "bundle.mjs"]
