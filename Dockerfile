# API (with the built UI), MCP server, scheduler, reporter, controller
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package*.json ./
RUN npm ci
COPY ui ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.19
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
 && uv pip install --system --no-cache -r /tmp/req.txt
COPY clew ./clew
COPY config ./config
COPY --from=ui /ui/dist ./ui/dist
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 CLEW_SCREENSHOTS=/data/screenshots
