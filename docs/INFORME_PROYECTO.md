# VinAnalytics Group
## Plataforma de Inteligencia Vitivinícola
### Informe del Proyecto — Guía para presentación en video (3 minutos)

---

## ¿Qué es VinAnalytics Group?

VinAnalytics Group es una plataforma de inteligencia de datos especializada en el análisis de reseñas de vinos a nivel mundial. Permite a analistas y gerentes explorar, filtrar y visualizar más de **300,000 reseñas** de vinos de 44 países, tomando decisiones basadas en datos reales del mercado vitivinícola.

---

## Problema que resuelve

El mercado del vino genera millones de reseñas y datos dispersos. Sin una herramienta centralizada, es difícil responder preguntas como:
- ¿Qué país produce los vinos mejor puntuados?
- ¿Cuáles son las variedades más costosas?
- ¿Qué bodegas tienen mayor consistencia de calidad?

VinAnalytics centraliza toda esa información en un dashboard analítico en tiempo real.

---

## Arquitectura del Sistema

El sistema está compuesto por **3 servicios** que corren en Docker:

| Componente | Función | Puerto |
|---|---|---|
| **PocketBase** | Base de datos de staging / fuente de datos | 8090 |
| **StarRocks** | Motor analítico OLAP (almacén de datos) | 9030 |
| **Flask** | Servidor web + API REST | 5000 |

### Modelo Estrella en StarRocks

Los datos se organizan en un **modelo estrella** optimizado para análisis:

- **fact_resenas** — Tabla de hechos con 308,724 reseñas
- **dim_pais** — 44 países vitivinícolas
- **dim_variedad** — 708 cepas/variedades distintas
- **dim_bodega** — 16,756 bodegas
- **dim_provincia** — 426 provincias
- **dim_region** — 1,230 regiones
- **dim_catador** — 20 catadores especializados

---

## Pipeline ETL

El flujo de datos sigue el patrón **Extracción → Transformación → Carga**:

```
CSV (129,971 registros)
    ↓
PocketBase (staging)
    ↓  E — Extracción
Parquet (wine_raw.parquet)
    ↓  T — Transformación
Dimensiones + Fact (parquet)
    ↓  L — Carga
StarRocks (modelo estrella)
```

Todo el pipeline se ejecuta desde el dashboard con un solo clic por etapa.

---

## Funcionalidades del Dashboard

### Indicadores Clave (KPIs)
- **Total Reseñas** — cantidad total de vinos evaluados
- **Puntuación Promedio** — calidad media del catálogo
- **Precio Promedio** — con rango mínimo y máximo
- **Total Países** — diversidad geográfica
- **Total Variedades** — diversidad de cepas

### Visualizaciones Analíticas
1. **Puntuación por País** — ranking de países por calidad promedio
2. **Top Variedades por Precio** — cepas más costosas del mercado
3. **Distribución de Puntuaciones** — histograma 80–100 puntos
4. **Top Bodegas** — bodegas con mayor consistencia de calidad

### Filtros de Análisis
- Por país, variedad, bodega, puntuación mínima y precio máximo
- Resultados en tiempo real sobre 300k+ registros

### Tabla de Reseñas
- Paginación de 308,724 registros
- Columnas: Título, Variedad, País, Bodega, Provincia, Puntos, Precio, Catador

---

## Sistema de Administración

Además del dashboard analítico, la plataforma incluye:

- **Login seguro** con roles (admin / analista / gerente)
- **Gestión de usuarios** — crear, editar, activar/desactivar
- **Auditoría** — registro de todas las acciones del sistema
- **Respaldos automáticos** — exportación JSON de datos del sistema

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | HTML5 + CSS3 + Chart.js |
| Backend | Python 3.13 + Flask 3.0 |
| Base analítica | StarRocks (OLAP, MySQL protocol) |
| Staging | PocketBase |
| ETL | pandas + PyArrow |
| Contenedores | Docker + Docker Compose |

---

## Guion sugerido para el video (3 minutos)

**[0:00 – 0:25] Introducción**
> "VinAnalytics Group es una plataforma de inteligencia de datos para el análisis del mercado vitivinícola. Permite explorar más de 300,000 reseñas de vinos de 44 países en tiempo real."

**[0:25 – 1:00] Arquitectura**
> "El sistema usa tres componentes en Docker: PocketBase como fuente de staging, StarRocks como motor analítico OLAP con un modelo estrella, y Flask como servidor web. Los datos se organizan en una tabla de hechos con 308,000 reseñas y seis tablas dimensionales."

**[1:00 – 1:40] Pipeline ETL**
> "El pipeline ETL tiene tres fases. Primero la extracción: los datos del CSV se cargan a PocketBase y se extraen a formato Parquet. Luego la transformación: pandas construye las dimensiones y resuelve las claves foráneas. Finalmente la carga: los datos van a StarRocks en lotes. Todo desde el dashboard con un clic."

**[1:40 – 2:20] Dashboard**
> "El dashboard muestra cinco KPIs en tiempo real: total de reseñas, puntuación promedio, precio promedio, países y variedades. Tiene cuatro gráficas: ranking de países, top variedades por precio, distribución de puntuaciones y mejores bodegas. Con filtros que funcionan sobre 300,000 registros instantáneamente."

**[2:20 – 2:50] Administración**
> "La plataforma también incluye un sistema de administración con login por roles, gestión de usuarios, auditoría de acciones y respaldos automáticos en JSON."

**[2:50 – 3:00] Cierre**
> "VinAnalytics Group es una solución completa de Business Intelligence para el sector vitivinícola, construida sobre tecnología moderna y lista para producción."

---

*VinAnalytics Group — Plataforma de Inteligencia Vitivinícola*
*Stack: Flask + StarRocks + PocketBase + Docker*
