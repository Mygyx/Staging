# Colaboración y reproducción

El repositorio principal es `chinook_staging_etl`. Las carpetas externas
`proyecto-oracle`, la copia del Vault y los bundles existentes son antecedentes,
no la implementación activa. No se eliminaron ni se sobrescribieron.

## Dos estudiantes, dos identidades reales

Cada estudiante configura su propia identidad Git y registra sus aportes reales.
No se modifican autores/fechas previos ni se crean commits en nombre del compañero.
Los siete commits iniciales permanecen accesibles en `oracle-baseline-361bb17`.
Los avances semanales y el tablero deben mantenerse durante el curso; los
commits de un solo día no demuestran varias semanas de actividad.

## Otro equipo de desarrollo

1. Clonar el remoto correcto cuando esté disponible.
2. Crear un entorno Python 3.13 e instalar requirements.
3. Copiar las configuraciones de ejemplo sin claves reales al archivo local.
4. Usar una base propia o acceso autorizado; no adoptar bases homónimas ajenas.
5. Comprobar `profile_sources.py --check` y ejecutar las pruebas locales.
6. Aprovisionar con permisos administrativos solo la base de este proyecto.
7. Ejecutar `run.ps1`, comprobar el lector y revisar evidencia PostgreSQL.

Para cambios de código usar una rama y revisión del compañero. No modificar
los CSV para que una prueba pase ni regenerar el manifiesto para ocultar cambios.

## Publicación pendiente

No hay remoto configurado. Solo cuando el usuario proporcione la URL correcta
se añadirá origin y se enviarán los commits. No publicar en otra cuenta ni
sobrescribir un repositorio con historial existente.

Los bundles anteriores representan versiones Oracle y no se regeneraron como
parte de esta migración. Se mantienen para recuperación; no equivalen a una
base de datos ni contienen .env, contraseñas, .venv o metadatos locales.

## Históricos y evidencias

`archive/oracle/` contiene código retirado del flujo activo. `evidence/oracle/`
y `docs/historico/oracle/` conservan los resultados anteriores, con enlaces
actualizados y etiquetas de motor. Para consultar un archivo original:

```powershell
git show oracle-baseline-361bb17:scripts/staging_core.py
```

Los resultados nuevos deben registrarse en `evidence/postgresql/`, indicando
qué pruebas se ejecutaron y cuáles están bloqueadas u omitidas. Una simulación
de unidad no debe presentarse como una carga real a PostgreSQL o como un flujo
Prefect Completed. No agregar archivos de `local/` o .env a Git.
