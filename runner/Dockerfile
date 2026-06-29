# Runner del pipeline: ETL + DBT + Great Expectations + populador ClickHouse.
# Imagen limpia (sin Airflow) → sin conflicto de dependencias. Versión base fija.
FROM python:3.11-slim

WORKDIR /app

# git lo requieren algunos adaptadores/paquetes de dbt al resolver dependencias.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY runner/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# El código del proyecto se monta en /app vía docker-compose (bind .:/app),
# así el `stage/` generado por la ingesta persiste entre tareas (mismo contenedor).
ENV PYTHONPATH=/app \
    DBT_PROFILES_DIR=/app/dbt_vinanalytics

# Contenedor de larga vida: Airflow ejecuta cada etapa con `docker exec`.
CMD ["tail", "-f", "/dev/null"]
