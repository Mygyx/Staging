# Pruebas y validaciones del Staging

## Fotografia y dos modos de ejecucion

Extraer CSV conserva los valores textuales y valida los hashes del manifiesto.
La fotografia mutable se vuelve a contrastar campo por campo contra los CSV,
sin aceptar cambios de su perfil. Se comprueba antes de conectar para cargar y
otra vez en la transaccion antes del COMMIT. Solo se confirma una carga cuya
fotografia, tablas, ordinales, catalogo y controles coinciden.

En una carga completa hay tres tareas: Extraer CSV, Cargar Staging y Validar
Staging. DELETE e INSERT y su validacion critica comparten una transaccion.
La ultima tarea abre otra conexion de solo lectura despues del COMMIT. Un error
en esa fase no revierte los datos ya confirmados.

Con `run.ps1 -ValidateOnly` no se ejecuta Cargar Staging ni se modifica PostgreSQL.
Se comprueba lo almacenado y se escriben evidencia y metadatos locales Prefect.

## Catalogo de la suite actual

Hay 45 casos: 25 locales y 20 de integracion PostgreSQL. Los subcasos monetarios
son parte de un caso, no tres pruebas independientes en el conteo de unittest.

| Grupo | Que demuestra |
| --- | --- |
| Configuracion y contrato | Variables, claves ocultas en errores, tablas y consultas CamelCase |
| Parser y hashes | Once fuentes intactas, UTF-8, limites entre campos, vacios y valores especiales |
| Fotografia en memoria | Rechazo de nombre cambiado, perfil/hash adulterado y representacion numerica distinta |
| Controles monetarios negativos | Rechazo de cambios en precio, cantidad y total de factura mediante Decimal |
| Aprovisionamiento | Rechazo de homonimos ajenos, motor incorrecto e instancia DW; permite otras bases |
| Seleccion de API Prefect | Conserva API existente sin iniciar servidor ni efectuar HTTP; no prueba una API real |
| Primera y segunda carga | DDL inicial correcto y recarga sin duplicar las doce tablas |
| Excepcion Python en carga | El callback de log falla tras la primera tabla; restaura la fotografia anterior |
| Error SQL real | Un INSERT de ordinal duplicado falla con UniqueViolation 23505; restaura todas las tablas |
| Cambio de memoria durante carga | Modificacion despues de insertar detectada antes del COMMIT y revertida |
| Corrupcion en tablas de prueba | Cambios en nombre y precio detectados y revertidos |
| Concurrencia y lectura | Bloqueo cooperativo y fotografia repetible durante una recarga |
| Lector | SELECT sobre fuentes; rechazo real de INSERT, UPDATE y DELETE en tablas aisladas |
| Permiso por columna | Detecta UPDATE sobre una columna aunque no exista el privilegio UPDATE de tabla |
| Prefect real | Flujo exitoso y tarea/flujo Failed ante error SQL; rollback y ausencia de reporte exitoso |

La prueba de error SQL inserta deliberadamente una PK existente en una tabla
del esquema de pruebas. No simula una excepcion psycopg: PostgreSQL la devuelve.
La prueba Prefect usa el motor real y un hook de fallo de la tarea para observar
Failed, ademas del estado Failed del flujo. Las pruebas unitarias `.fn` se
conservan para la semantica de los reportes, con ese alcance limitado.

## Aislamiento y autorizacion

Para ejecutar integracion se requieren RUN_PG_INTEGRATION=1 y
STG_TEST_SCHEMA_AUTHORIZED=1, credenciales limitadas y autorizacion del usuario.
Cada caso crea un esquema stg_test_* unico y marcado dentro de chinook_staging.
Solo el esquema creado por ese caso puede eliminarse. Se compara la firma de
public antes y despues de la suite. Ninguna prueba corrompe o vacia public.

Los GRANT de preparacion del lector se limitan a objetos de cada esquema de
pruebas y desaparecen al eliminarlo. No se alteran atributos ni membresias de
roles, permisos de public, credenciales ni configuracion de la instancia.

Los casos Prefect pueden reutilizar una API existente. El temporal empleado en
esta sesion fue autorizado solo para pruebas y se detiene al terminar. No es
una instalacion permanente ni una configuracion del servidor DW.

## Como interpretar las evidencias

Los reportes unit-tests, integration-tests y cleanup-* corresponden a versiones
y ejecuciones anteriores. Sus 34 pruebas no se reinterpretan como si incluyeran
los casos nuevos. final-fixes-unit-tests registra la ejecucion local anterior
al caso de permisos por columna; sus 19
integraciones omitidas no se cuentan como aprobadas. final-fixes-integration-tests
registra la primera suite completa de esta correccion, con 44 casos.
final-fixes-complete-tests registra la suite ampliada final de 45 casos, que
incluye el rechazo de permisos por columna. Ningun reporte anterior se reescribe
para simular una cobertura que todavia no existia en aquella ejecucion.

Los mensajes ERROR, estados Failed y SQLSTATE 23505 son esperados en el caso
negativo de Prefect. El resumen de unittest y el JSON de resultados distinguen
esa comprobacion exitosa de una prueba fallida.

Estas pruebas no demuestran desconexiones de red durante COMMIT, permisos sobre
todos los objetos del servidor, acceso desde las PCs DW, instalacion en otra
computadora, tablero Scrum ni colaboracion de otro autor. Esos aspectos requieren
sus propias comprobaciones y no se presentan como terminados.
