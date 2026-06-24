#!/usr/bin/env python3
"""Parchea coreBundle.js de Playwright para evitar crash con pageError.location undefined.

Bug: Playwright 1.60.0 con Firefox en Node.js v22+ crashea cuando una página
lanza un pageError sin location (ej. errores de sintaxis en scripts inline).
El driver asume que pageError.location siempre existe y explota al validar el
esquema del evento.

El parche reemplaza:
    location: { url: pageError.location.url, ... }
por:
    location: pageError.location ? { url: ... } : { url: '', line: 0, column: 0 }

Idempotente: no modifica si el parche ya está aplicado.
Se pierde con cada `pip install` o `pip upgrade` de playwright — volver a ejecutar.
"""

import sys
from pathlib import Path


def find_core_bundle() -> Path | None:
    """Localiza coreBundle.js dentro del paquete playwright instalado."""
    try:
        import playwright

        p = Path(playwright.__file__).parent / "driver" / "package" / "lib" / "coreBundle.js"
        if p.exists():
            return p
    except ImportError:
        pass

    # Fallback: buscar en .venv
    for p in Path.cwd().rglob("coreBundle.js"):
        if "playwright" in str(p) and "driver" in str(p):
            return p
    return None


ORIGINAL = """            location: {
              url: pageError.location.url,
              line: pageError.location.lineNumber,
              column: pageError.location.columnNumber
            }"""

REPLACEMENT = """            location: pageError.location ? {
              url: pageError.location.url,
              line: pageError.location.lineNumber,
              column: pageError.location.columnNumber
            } : { url: '', line: 0, column: 0 }"""


def main() -> int:
    core = find_core_bundle()
    if core is None:
        print("ERROR: coreBundle.js no encontrado. ¿Playwright está instalado?")
        return 1

    content = core.read_text()

    if REPLACEMENT in content:
        print(f"✅ Parche ya aplicado — {core}")
        return 0

    if ORIGINAL not in content:
        print("ERROR: patrón original no encontrado en coreBundle.js. "
              "Versión de Playwright no soportada o distinta estructura.")
        return 1

    content = content.replace(ORIGINAL, REPLACEMENT)
    core.write_text(content)

    # Verify
    if REPLACEMENT in core.read_text():
        print(f"✅ Parche aplicado — {core}")
        return 0
    else:
        print("ERROR: parche no se aplicó correctamente")
        return 1


if __name__ == "__main__":
    sys.exit(main())
