# Colaboración y reproducción

El repositorio principal es `chinook_staging_etl`: CSV, Python/Prefect y
PostgreSQL. El código, pruebas y documentación vigentes están en este repositorio.

## Dos estudiantes, dos identidades reales

Cada estudiante configura su propia identidad Git y registra sus aportes reales.
No se modifican autores/fechas previos ni se crean commits en nombre del compañero.
El historial detallado permanece en la rama local
`backup/historial-completo-4332b0f`. Las etiquetas locales
`oracle-baseline-361bb17`, `pre-cleanup-b54ab4e` y `pre-final-fixes-d9f66a9`
conservan puntos anteriores a la migración, limpieza y correcciones finales.
La publicación conserva el commit de CSV de Miguel y cinco commits posteriores
agrupados por etapas reales, con formato `tipo(alcance): descripción`.
Los avances semanales y el tablero deben mantenerse durante el curso; los
commits de un solo día no demuestran varias semanas de actividad.

## Otro equipo de desarrollo

1. Clonar `https://github.com/Mygyx/Staging.git` y entrar en `Staging`.
2. Crear un entorno Python 3.13 e instalar requirements.
3. Copiar las configuraciones de ejemplo sin claves reales al archivo local.
4. Usar una base propia o acceso autorizado; no adoptar bases homónimas ajenas.
5. Comprobar `profile_sources.py --check` y ejecutar las pruebas locales.
6. Aprovisionar con permisos administrativos solo la base de este proyecto.
7. Ejecutar `run.ps1`, comprobar el lector y revisar evidencia PostgreSQL.

Para cambios de código usar una rama y revisión del compañero. No modificar
los CSV para que una prueba pase ni regenerar el manifiesto para ocultar cambios.

## Repositorio remoto y colaboración

El remoto autorizado es [Mygyx/Staging](https://github.com/Mygyx/Staging).
Su commit inicial se conserva, incluida su autoría. Los cinco commits del
proyecto se añaden a continuación, sin forzar ni sobrescribir la rama remota.

Para un aporte nuevo, cada integrante crea su propia rama y solicita revisión:

```powershell
git clone https://github.com/Mygyx/Staging.git
cd Staging
git switch -c feat/descripcion-del-aporte
```

Después de implementar y verificar su cambio, registra únicamente los archivos
de su aporte con `git add <rutas>`, usa un mensaje como
`feat(validacion): comprobar un nuevo caso de integridad` y publica su rama con
`git push -u origin feat/descripcion-del-aporte`. La revisión y el merge se
realizan mediante un pull request; no se crean aportes en nombre de otra persona.

Las ramas `backup/*` y las etiquetas de recuperación se mantienen locales.
Para publicar `main` se usa `git push -u origin main`, sin `--all`, `--tags` ni
`--force`. Las configuraciones `.env`, `.venv/` y `local/` siguen excluidas.

## Históricos y evidencias

El código y las evidencias de Oracle se retiraron del árbol de trabajo una vez
verificada la implementación PostgreSQL. Permanecen recuperables desde Git.
En la PC que conserva las referencias locales, se puede consultar un archivo
anterior a la limpieza sin cambiar de versión:

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
