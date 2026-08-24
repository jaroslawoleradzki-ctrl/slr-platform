# Stage 1: Build Frontend SPA
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY VERSION ./VERSION
COPY frontend ./frontend
WORKDIR /build/frontend
ENV VITE_API_BASE_URL="/api/v1"
RUN npm run build

# Stage 2: Final Runtime with Python FastAPI & Frontend Static Files
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md VERSION ./
COPY migrations ./migrations
COPY app ./app
COPY projects ./projects
COPY assets/fonts ./assets/fonts
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
RUN mkdir -p /app/data
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
