FROM node:22-alpine

WORKDIR /app/web

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG API_INTERNAL_BASE_URL=http://api:8000

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV API_INTERNAL_BASE_URL=${API_INTERNAL_BASE_URL}

COPY web/ /app/web/

RUN corepack enable && \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi && \
    npm run build && \
    mkdir -p .next/standalone/.next && \
    cp -a .next/static .next/standalone/.next/static && \
    if [ -d public ]; then cp -a public .next/standalone/public; fi

CMD ["node", ".next/standalone/server.js"]
