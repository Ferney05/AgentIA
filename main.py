import uvicorn
import os
import sys

# Añadir el directorio actual al path para que reconozca el módulo 'kyber'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Ejecuta la aplicación FastAPI desde el módulo kyber.web
    # Host 0.0.0.0 permite acceso desde otros dispositivos en la red
    # Port 8000 es el puerto por defecto
    uvicorn.run("kyber.web:app", host="127.0.0.1", port=8000, reload=True)
