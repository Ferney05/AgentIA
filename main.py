import os
import sys

# Añadir el directorio actual al path para que reconozca el módulo 'kyber'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importamos 'app' desde el módulo web para que Render/Uvicorn lo vean
from kyber.web import app

if __name__ == "__main__":
    import uvicorn
    # Ejecuta la aplicación FastAPI
    # Host 0.0.0.0 permite acceso desde internet (importante para Render)
    # Port 8000 es el puerto local, Render usará el que necesite
    uvicorn.run(app, host="0.0.0.0", port=8000)
