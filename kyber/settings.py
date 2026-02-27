import os
from pathlib import Path


def cargar_env(ruta: str = ".env") -> None:
    path = Path(ruta)
    if not path.exists():
        return

    contenido = path.read_text(encoding="utf-8")
    for linea in contenido.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor
    _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"

