# Restricted fictional-data staging only; this is not a production deployment.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nginx openssl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system literacy && useradd --system --gid literacy --home-dir /app literacy
WORKDIR /app
COPY --chown=literacy:literacy prototype/ ./prototype/
COPY --chown=literacy:literacy content/ ./content/
COPY --chown=literacy:literacy registry/ ./registry/
COPY --chown=literacy:literacy deploy/render/ ./deploy/render/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER literacy
CMD ["python3", "-m", "deploy.render.start"]
