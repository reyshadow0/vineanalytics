-- Test singular: el puntaje en Fact_Puntuacion debe estar en 80..100 (RT-06).
-- DBT considera el test fallido si esta consulta devuelve filas.
select id_puntuacion, puntaje
from {{ ref('fct_puntuacion') }}
where puntaje < 80 or puntaje > 100
