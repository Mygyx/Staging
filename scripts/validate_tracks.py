
"""Validaciones de calidad de los datos de Track."""

from decimal import Decimal, InvalidOperation

from profile_sources import ROOT, TABLE_NAMES, read_source


def validar_tracks(registros):
    errores = []
    ids = set()
    bytes_vacios = 0

    for numero, track in enumerate(registros, start=1):
        identificador = track["TrackId"]
        referencia = f"Track fila {numero} (ID {identificador})"

        # Comprobar identificador positivo y unico
        try:
            track_id = int(identificador)

            if track_id <= 0:
                raise ValueError("ID no positivo")

            if track_id in ids:
                raise ValueError("ID duplicado")

            ids.add(track_id)

        except ValueError as error:
            errores.append(f"{referencia}: {error}")

        # La duracion debe ser un entero positivo
        try:
            duracion = int(track["Milliseconds"])

            if duracion <= 0:
                raise ValueError("Duracion no positiva")

        except ValueError:
            errores.append(f"{referencia}: duracion invalida")

        # El precio debe ser numerico, finito y no negativo
        try:
            precio = Decimal(track["UnitPrice"])

            if not precio.is_finite() or precio < 0:
                raise ValueError("Precio invalido")

        except (InvalidOperation, ValueError):
            errores.append(f"{referencia}: precio invalido")

        # Bytes es opcional, pero debe ser valido si existe
        tamano = track["Bytes"]

        if tamano == "":
            bytes_vacios += 1
        else:
            try:
                bytes_archivo = int(tamano)

                if bytes_archivo < 0:
                    raise ValueError("Tamano negativo")

            except ValueError:
                errores.append(f"{referencia}: Bytes invalido")

    if errores:
        detalle = "\n".join(errores[:10])

        raise ValueError(
            f"Se encontraron {len(errores)} errores en Track:\n"
            f"{detalle}"
        )

    return {
        "tracks_revisados": len(registros),
        "bytes_vacios": bytes_vacios,
        "errores": 0
    }


def validar_tracks_snapshot(snapshot):
    """Valida Track usando los registros extraidos por el ETL."""

    tabla = snapshot["tables"][TABLE_NAMES["Track"]]

    registros = [
        dict(zip(tabla["header"], fila))
        for fila in tabla["rows"]
    ]

    return validar_tracks(registros)


def main():
    """Permite ejecutar la validacion directamente sobre el CSV."""

    ruta = ROOT / "data" / "raw" / "Track.csv"

    encabezados, filas, _ = read_source(ruta)

    registros = [
        dict(zip(encabezados, fila))
        for fila in filas
    ]

    resultado = validar_tracks(registros)

    print("=== VALIDACION DE TRACK ===")
    print(f"Tracks revisados: {resultado['tracks_revisados']}")
    print(f"Campos Bytes vacios: {resultado['bytes_vacios']}")
    print(f"Errores encontrados: {resultado['errores']}")
    print("Resultado: datos validos")


if __name__ == "__main__":
    main()
