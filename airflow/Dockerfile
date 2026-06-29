# Imagen de Airflow SOLO para orquestar (Fase 3, rev. runner).
# Base fijada (Princ. VIII / RT-17): Airflow 2.9.3 sobre Python 3.11.
# No instala GE/DBT/pandas: las etapas pesadas corren en el contenedor `runner`
# vía `docker exec`. Así se evita el conflicto de pip al construir Airflow.
FROM apache/airflow:2.9.3-python3.11

USER root
# CLI de Docker para que las tareas hagan `docker exec vinanalytics-runner ...`.
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
USER airflow
