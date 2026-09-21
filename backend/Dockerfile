FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.lock .
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.lock
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 mama && mkdir -p /data/files && chown -R mama:mama /data
WORKDIR /app
COPY --from=build /wheels /wheels
COPY requirements.lock .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock && rm -rf /wheels
COPY --chown=mama:mama . .
USER mama
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=127.0.0.1","--no-access-log"]
