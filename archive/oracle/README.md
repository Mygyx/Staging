# Antecedente Oracle

Estos archivos están fuera del flujo activo PostgreSQL. No ejecutarlos contra
los servidores actuales ni confundir sus resultados con pruebas PostgreSQL.
La versión completa original es `oracle-baseline-361bb17`, que conserva los
siete commits previos. Los instaladores, SQL, generador y pruebas se preservan
aquí como antecedentes. Sus imports/rutas pueden depender de aquella versión.

No se eliminaron Oracle XE, bases, esquemas, usuarios ni las credenciales
cifradas que ya existían en local/. Las carpetas externas y bundles siguen
intactos. No se utiliza una credencial Oracle para autenticar PostgreSQL.
