# Entrega y colaboración

## Qué recibe el compañero

- `data/raw/`: fotografía exacta de los 11 CSV.
- `data/manifest.json` y `docs/fuentes.md`: estructura, conteos, hashes y calidad.
- `scripts/staging_flow.py`: orquestación Prefect.
- `scripts/staging_core.py`: carga Oracle y comparación de cada campo.
- `sql/`: DDL, carga y validación SQL reproducibles.
- `evidence/`: resultados reales de las ejecuciones y pruebas.
- `README.md`: instalación, conexión y ejecución desde cero.

Las tablas fuente usan texto. Ejemplo: `STG_INVOICE.Total` mantiene el formato
del CSV. Al transformar al DW, se debe convertir con un formato explícito y
documentar las reglas. No se debe limpiar la fuente ni sobrescribir este staging.

## Repositorio remoto

El remoto del equipo está pendiente de definir. Cuando exista, desde esta carpeta:

```powershell
git remote add origin URL_REAL_DEL_REPOSITORIO_VACIO
git push -u origin main
```

Si el repositorio del equipo ya tiene historial, no uses `--force`. Clónalo y
acuerda la integración por rama/PR, conservando los commits de este staging.

El compañero puede clonar el repositorio remoto e instalar las dependencias:

```powershell
git clone URL_REAL_DEL_REPOSITORIO
cd NOMBRE_REAL_DEL_REPOSITORIO
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cada integrante debe usar su identidad real de Git y hacer commits de su propio
trabajo. No se cambian las fechas ni se simulan aportes de otros integrantes.

## Transporte sin remoto

`staging-oracle.bundle` junto a la carpeta `proyecto-oracle` contiene el historial
completo y los archivos versionados. Se puede enviar al compañero y clonar:

```powershell
git clone .\staging-oracle.bundle invacom-staging
```

Después de nuevos commits se regenera con:

```powershell
git bundle create ..\staging-oracle.bundle --all
git bundle verify ..\staging-oracle.bundle
```

No se comparte `.venv/` ni `local/`; en particular, no se comparte la credencial.

## Backlog sugerido para las semanas siguientes

Este listado es una propuesta; el equipo debe crear y mantener el tablero real
en GitHub Projects, Trello u otra herramienta acordada. Cada tarjeta debería
tener responsable, semana, criterio de aceptación y vínculo al commit o PR.

| Trabajo pendiente del equipo | Criterio de aceptación |
| --- | --- |
| Publicar repositorio remoto y crear tablero | URL compartida y acceso de integrantes |
| Revisar entrega staging en otra máquina | Flujo Prefect termina y compara 15.607 registros |
| Definir objetivos de negocio y granularidad | Decisiones aprobadas y documentadas |
| Diseñar modelo dimensional | Diagrama con dimensiones, hechos y medidas |
| Implementar transformaciones con Prefect | Reglas justificadas y resultados comprobados |
| Conectar Excel y crear tablas dinámicas | Consultas responden los objetivos de negocio |
| Documento APA 7 y defensa | Documento único con referencias y evidencia real |

La revisión semanal debe mostrar avances de esa semana. El README y los commits
de esta entrega no reemplazan el tablero ni las ceremonias del equipo.
