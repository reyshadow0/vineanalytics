# Proyecto: RETAILYTICS S.A.

## ¿Qué es este proyecto?
Sistema web para cargar un dataset CSV de comportamiento de usuarios 
retail a una base de datos PostgreSQL, y visualizar los datos desde 
una página web.

## Stack tecnológico
- Python (backend y carga de datos)
- PostgreSQL (base de datos)
- Flask (página web)
- pandas y SQLAlchemy (manejo de datos)

## Dataset
Archivo: retail_intelligence.csv
Columnas principales: Session_ID, User_ID, User_Action, Category, 
Brand, Price, Timestamp, Channel, Device, Region, Traffic_Source, 
is_conversion, drop_off_flag, session_length, interaction_count, 
time_spent_sec

## Base de datos
Nombre: retailytics_db
Usuario: postgres
Puerto: 5432