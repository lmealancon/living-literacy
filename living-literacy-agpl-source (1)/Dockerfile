# Synthetic-data local demo only. Not a production deployment.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system literacy && useradd --system --gid literacy --home-dir /app literacy \
    && mkdir /data && chown literacy:literacy /data
COPY --chown=literacy:literacy prototype/ ./prototype/
COPY --chown=literacy:literacy content/ ./content/
COPY --chown=literacy:literacy registry/ ./registry/
USER literacy
EXPOSE 8765
ENTRYPOINT ["python3", "-m", "prototype.app_server"]
CMD ["--db", "/data/demo.sqlite3", "--port", "8765", "--container-demo"]
