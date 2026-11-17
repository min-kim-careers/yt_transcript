# 1. Build the Svelte UI
FROM node:22-slim AS web
RUN npm i -g pnpm@10.8.0
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# 2. Python server
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY --from=web /web/dist web/dist
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
