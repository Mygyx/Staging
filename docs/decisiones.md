# Decisiones de PostgreSQL Staging

1. La fuente autoritativa sigue siendo `data/raw`: once CSV UTF-8 preservados
   byte por byte y protegidos por los SHA-256 originales. `csv.reader` mantiene
   comillas internas, comas, espacios, Unicode y representaciones numéricas.
2. Cada columna fuente es TEXT con el mismo encabezado CamelCase entre comillas.
   No se usa inferencia de Pandas, DATE, NUMERIC ni VARCHAR limitado. No hay PK,
   FK o unicidad de negocio que rechace una fila fuente. La única PK de cada
   fuente es el ordinal técnico `CSV_ROW_NUMBER`, empezando en 1.
3. Los vacíos son `''`, distintos de NULL. El literal `NULL` se conservaría como
   texto. El DW decidirá posteriormente cómo tratar los faltantes y convertir tipos.
4. Hay once tablas fuente y una de metadatos `etl_source_file`. El catálogo se
   reemplaza en la misma transacción que la fotografía de datos. No es historial
   de cambios; las ejecuciones se conservan en las evidencias y en Prefect.
5. Full Refresh usa DELETE + INSERT en una única transacción PostgreSQL, con un
   advisory lock transaccional por proyecto/esquema. El bloqueo impide dos
   recargas de este mismo flujo y se libera al terminar la transacción. No usa
   TRUNCATE ni elimina/recrea tablas existentes. Se preservan esquema y permisos.
6. La primera carga puede crear las doce tablas en la misma transacción. Una
   estructura parcial, distinta o con objetos ajenos provoca un error antes de
   borrar datos. El ETL exige nuestra base marcada y rechaza superusuarios.
7. La validación crítica compara campo por campo y ordinales antes del COMMIT.
   Recalcula hashes de filas, revisa tipos, PK, catálogo, conteos y controles con
   Decimal. Se preservan 15607 filas, 66439 campos, 1339 vacíos, 24 códigos
   postales con ceros iniciales y 8 campos con espacio final. Totales: 2328.60.
   La fotografia en memoria se vuelve a comparar contra los CSV y sus SHA-256
   del manifiesto al iniciar y dentro de la validacion anterior al COMMIT. Una
   modificacion en memoria no puede legitimarse cambiando solamente su perfil.
8. La tarea visible final hace una verificación independiente y genera evidencia
   después del COMMIT. Su fallo no revierte datos confirmados. No hay conexiones
   abiertas serializadas por Prefect: cada tarea abre y cierra las suyas.
9. El lector utiliza una transacción REPEATABLE READ READ ONLY para obtener una
   fotografía consistente de las once tablas, incluso mientras otra conexión
   refresca mediante DELETE + INSERT. Las pruebas verifican este comportamiento.
10. El entorno de staging es independiente del DW. El proyecto no configura ni
    modifica el servidor del DW, sus transformaciones, servicios o firewall.
    El equipo mantiene instancias distintas como decision propia de despliegue;
    dos repositorios separados no obligan por si solos a esa separacion fisica.
    El aprovisionador protege esa decision rechazando los nombres DW conocidos,
    permite bases ajenas y exige revisar la instancia antes de crear objetos.
    Ambos repositorios pueden compartir una API de monitoreo Prefect.
11. Las pruebas destructivas requieren dos indicadores explícitos y utilizan
    esquemas aleatorios propios dentro de chinook_staging, nunca public.
12. La rama publicada conserva el commit fuente de Miguel y cinco commits
    posteriores agrupados con formato `tipo(alcance): descripción`. El historial
    detallado de 17 commits permanece en la rama local
    `backup/historial-completo-4332b0f`, junto con las etiquetas de recuperación.
    Los originales conservan sus autores y fechas; agruparlos genera nuevos
    identificadores y no acredita semanas distintas ni aportes de otra persona.
    El árbol activo usa PostgreSQL. Las credenciales reales se excluyen de Git.

Referencias oficiales: [psycopg y transacciones](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[identificadores seguros](https://www.psycopg.org/psycopg3/docs/api/sql.html),
[aislamiento PostgreSQL](https://www.postgresql.org/docs/17/transaction-iso.html).
