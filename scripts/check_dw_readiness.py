
"""Comprueba la preparación de ventas para el Data Warehouse."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from profile_sources import ROOT, read_source


def obtener_registros(nombre):
    ruta = ROOT / "data" / "raw" / f"{nombre}.csv"
    columnas, filas, _ = read_source(ruta)
    return [dict(zip(columnas, fila)) for fila in filas]


def verificar_ventas(registros=None):
    if registros is None:
        facturas = obtener_registros("Invoice")
        detalles = obtener_registros("InvoiceLine")
    else:
        facturas = registros["Invoice"]
        detalles = registros["InvoiceLine"]
        
    errores = []
    totales_facturas = {}
    ventas_calculadas = defaultdict(lambda: Decimal("0"))

    # Verificar fechas y totales de facturas
    for factura in facturas:
        identificador = factura["InvoiceId"]

        try:
            int(identificador)
            datetime.fromisoformat(factura["InvoiceDate"])
            total = Decimal(factura["Total"])

            if not total.is_finite() or total < 0:
                raise ValueError("Total inválido")

            if identificador in totales_facturas:
                raise ValueError("Factura duplicada")

            totales_facturas[identificador] = total

        except (ValueError, InvalidOperation) as error:
            errores.append(
                f"Factura {identificador}: {error}"
            )

    # Comprobar cantidades e importes de cada línea
    for detalle in detalles:
        identificador = detalle["InvoiceLineId"]
        factura_id = detalle["InvoiceId"]

        try:
            int(identificador)
            int(factura_id)
            cantidad = int(detalle["Quantity"])
            precio = Decimal(detalle["UnitPrice"])

            if cantidad <= 0 or not precio.is_finite() or precio < 0:
                raise ValueError("Cantidad o precio inválido")

            ventas_calculadas[factura_id] += cantidad * precio

        except (ValueError, InvalidOperation) as error:
            errores.append(
                f"Línea {identificador}: {error}"
            )

    # Comparar cada factura con la suma de sus líneas
    for factura_id, total in totales_facturas.items():
        calculado = ventas_calculadas[factura_id]

        if calculado != total:
            errores.append(
                f"Factura {factura_id}: "
                f"esperado {total}, calculado {calculado}"
            )

    for factura_id in ventas_calculadas:
        if factura_id not in totales_facturas:
            errores.append(
                f"Líneas asociadas a factura inexistente: {factura_id}"
            )

    print("\n=== VALIDACIÓN PREVIA AL DATA WAREHOUSE ===")
    print(f"Facturas revisadas: {len(facturas)}")
    print(f"Líneas revisadas: {len(detalles)}")
    print(f"Ventas calculadas: {sum(ventas_calculadas.values())}")
    print(f"Errores encontrados: {len(errores)}")

    for error in errores[:10]:
        print(f"ERROR: {error}")

    if errores:
        raise SystemExit(1)

    print("Resultado: datos de ventas válidos para transformación")


if __name__ == "__main__":
    verificar_ventas()
