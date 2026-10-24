# Colaboración y reproducción

El repositorio principal es `chinook_staging_etl`: CSV, Python/Prefect y
PostgreSQL. El código, pruebas y documentación vigentes están en este repositorio.

## Dos estudiantes, dos identidades reales

Cada estudiante configura su propia identidad Git y registra sus aportes reales.
No se modifican autores/fechas previos ni se crean commits en nombre del compañero.
Los siete commits iniciales permanecen accesibles en `oracle-baseline-361bb17`;
los once anteriores a la limpieza están en `pre-cleanup-b54ab4e`.
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

## Históricos y evidencias

El código y las evidencias de Oracle se retiraron del árbol de trabajo una vez
verificada la implementación PostgreSQL. Permanecen recuperables desde Git.
Para consultar un archivo anterior a la limpieza sin cambiar de versión:

```powershell
git show pre-cleanup-b54ab4e:archive/oracle/scripts/generate_sql.py
```

La [nota de limpieza](limpieza-repositorio.md) documenta qué se retiró y qué
archivos locales se preservaron. No ejecutar instrucciones históricas como
parte de la instalación actual.

Los resultados nuevos deben registrarse en `evidence/postgresql/`, indicando
qué pruebas se ejecutaron y cuáles están bloqueadas u omitidas. Una simulación
de unidad no debe presentarse como una carga real a PostgreSQL o como un flujo
Prefect Completed. No agregar archivos de `local/` o .env a Git.
