KYBER · Agente de Gmail con IA (FastAPI + Gemini)
=================================================

Este proyecto es un panel web para automatizar la bandeja de entrada de Gmail usando IA (Gemini) y borradores en Gmail.  
Incluye:
- Panel web en FastAPI + Jinja2.
- Conexión directa a Gmail vía IMAP para leer correos y crear borradores.
- Motor de reglas y plantillas de respuesta.
- Base de datos SQLite para usuarios, reglas, respuestas y logs.

> Ruta del proyecto: `c:\Users\FerneyEnriqueBarbosa\Documents\AgentIA`


Requisitos previos
------------------

Instala y verifica todo esto **antes** de levantar el proyecto:

- **Python 3.11+** (recomendado)
  - Windows: descarga desde https://www.python.org/downloads/  
    Durante la instalación marca la casilla **“Add Python to PATH”**.
- **Git** (opcional, solo si vas a versionar el código).
- **Cuenta de Gmail** con:
  - Acceso IMAP habilitado.
  - Contraseña de aplicación (no la contraseña normal de la cuenta).
- **Cuenta de Google AI Studio** para usar **Gemini**:
  - Crea una API key en https://aistudio.google.com

Opcional pero recomendado:

- **Editor de código** como VS Code.
- Navegador moderno (Chrome, Edge, Firefox).


Clonar o copiar el proyecto
---------------------------

Si el código ya está en `c:\Users\FerneyEnriqueBarbosa\Documents\AgentIA`, puedes saltar este paso.

Con Git:

```bash
git clone <URL_DEL_REPO> AgentIA
cd AgentIA
```

En Windows PowerShell:

```powershell
cd C:\Users\FerneyEnriqueBarbosa\Documents\AgentIA
```


Crear y activar el entorno virtual
----------------------------------

### Windows (PowerShell)

1. Crear el entorno virtual en la carpeta del proyecto:

```powershell
cd C:\Users\FerneyEnriqueBarbosa\Documents\AgentIA
python -m venv .venv
```

2. Activar el entorno virtual:

```powershell
.venv\Scripts\Activate.ps1
```

Si ves un error de políticas de ejecución, ejecuta primero en PowerShell **como Administrador**:

```powershell
Set-ExecutionPolicy RemoteSigned
```

Acepta con `Y`, cierra PowerShell, ábrelo de nuevo y vuelve a activar:

```powershell
cd C:\Users\FerneyEnriqueBarbosa\Documents\AgentIA
.venv\Scripts\Activate.ps1
```

Cuando el entorno esté activo verás algo como `(.venv)` al inicio de la línea.

### macOS / Linux (bash/zsh)

```bash
cd ~/AgentIA
python3 -m venv .venv
source .venv/bin/activate
```


Instalar dependencias
---------------------

El proyecto usa, entre otras, estas librerías:

- `fastapi`
- `uvicorn[standard]`
- `starlette`
- `jinja2`
- `google-generativeai`

Si ya tienes las dependencias instaladas en `.venv` no hace falta repetir este paso.  
Si no, instala manualmente con:

```bash
pip install fastapi "uvicorn[standard]" starlette jinja2 google-generativeai
```

En el futuro, si agregas un `requirements.txt`, podrás usar:

```bash
pip install -r requirements.txt
```


Configurar variables de entorno (.env)
--------------------------------------

El archivo [`kyber/settings.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/settings.py#L1-L22) carga las variables desde un archivo `.env` en la raíz del proyecto.

1. Crea el archivo `.env` en `C:\Users\FerneyEnriqueBarbosa\Documents\AgentIA\.env`
2. Coloca dentro algo como:

```env
# Credenciales de Gmail
KYBER_GMAIL_USER=tu_correo@gmail.com
KYBER_GMAIL_APP_PASSWORD=tu_clave_de_aplicacion

# API key de Gemini
GEMINI_API_KEY=tu_api_key_de_gemini

# Nombre opcional de la empresa (se usa para limpiar borradores)
KYBER_COMPANY_NAME=Nombre de tu empresa

# Configuración de batch del escaneo (opcional)
KYBER_SCAN_BATCH=10
KYBER_SCAN_MAX=100

# Clave de sesión para FastAPI/Starlette
KYBER_SESSION_SECRET=una_clave_larga_y_secreta
```

Notas importantes:

- **KYBER_GMAIL_USER** debe ser el correo exacto de Gmail.
- **KYBER_GMAIL_APP_PASSWORD** es la contraseña de aplicación generada en la cuenta de Google (no tu clave normal).
- **GEMINI_API_KEY** es obligatoria; si falta, [`kyber/ai.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/ai.py#L1-L18) lanza un `RuntimeError`.


Inicializar la base de datos
----------------------------

La base de datos SQLite (por defecto `kyber.db`) se crea y migra automáticamente en el evento de startup de FastAPI:

- Ver [`kyber/web.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/web.py#L82-L85):

```python
@app.on_event("startup")
def startup() -> None:
    crear_base_de_datos()
```

No necesitas ejecutar migraciones manuales: al levantar el servidor por primera vez se crearán las tablas necesarias (`usuarios`, `reglas`, `respuestas`, `logs`, etc.) según [`kyber/db.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/db.py).


Levantar el servidor (FastAPI + Uvicorn)
----------------------------------------

Con el entorno virtual activado y las variables en `.env`:

```bash
cd C:\Users\FerneyEnriqueBarbosa\Documents\AgentIA
uvicorn kyber.web:app --reload
```

Explicación:

- `kyber.web:app` apunta al objeto `app = FastAPI()` definido en [`kyber/web.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/web.py#L47).
- `--reload` recarga automáticamente el servidor al guardar cambios en el código (útil en desarrollo).

Luego abre en el navegador:

- Panel principal: http://127.0.0.1:8000/


Registro y login de usuario
---------------------------

El sistema maneja usuarios en la tabla `usuarios` y usa sesiones de Starlette.

Flujo:

1. Abre: `http://127.0.0.1:8000/auth/register`
   - Rellena correo y contraseña.
   - El usuario se crea mediante [`crear_usuario`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/db.py#L236-L253) y se guarda en SQLite.
2. Tras registrarte, el sistema te redirige al panel (`/`).
3. Para cerrar sesión: `POST /auth/logout` (desde el botón de logout en la UI).
4. Para iniciar sesión de nuevo: `http://127.0.0.1:8000/auth/login`


Uso del panel KYBER
-------------------

Una vez logueado:

- **Dashboard (`view=dashboard`)**:
  - Muestra número de borradores creados, reglas activas y un gráfico de “borradores por periodo”.
  - Tabla de historial reciente con:
    - Fecha, remitente, asunto, categoría (`COTIZACIONES`, `ANUNCIO`, `GENERAL`), acción (`BORRADOR` o `NADA`) e idioma.
  - Botón **“Escanear una vez”**:
    - Envia `POST /scan` que ejecuta `_ejecutar_scan()` en [`kyber/web.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/web.py#L259-L325).
    - El escaneo:
      - Lee correos no leídos vía IMAP.
      - Pasa cada correo a la IA (`procesar_correo_con_ia` en [`kyber/ai.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/ai.py#L62-L199)).
      - Crea borradores en Gmail (`crear_borrador` en [`kyber/gmail_client.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/gmail_client.py#L260-L287)) cuando corresponde.
      - Registra logs en la base de datos.

- **Reglas (`view=rules`)**:
  - Formularios para crear/editar reglas que educan al agente (tono, políticas, etc.).
  - Cada regla tiene:
    - `clave`, `instruccion`, `prioridad (1–5)`.
  - Endpoint de sugerencia: `POST /rules/suggest` llama a `sugerir_clave_prioridad` en [`kyber/ai.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/ai.py#L200-L234).

- **Respuestas (`view=respuestas`)**:
  - Plantillas predefinidas que la IA puede usar tal cual (especialmente para cotizaciones incompletas).
  - CRUD completo sobre las respuestas almacenadas en SQLite.


Integración con Gmail
---------------------

Toda la lógica de Gmail está en [`kyber/gmail_client.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/gmail_client.py#L1-L323).

Funciones clave:

- `obtener_ids_no_leidos(max_total)`:
  - Se conecta al IMAP de Gmail (`imap.gmail.com`) usando `KYBER_GMAIL_USER` y `KYBER_GMAIL_APP_PASSWORD`.
  - Devuelve los IDs de correos no leídos.
- `obtener_correos_por_ids(ids)`:
  - Descarga cada correo y extrae remitente, asunto, cuerpo (texto plano o HTML saneado), imágenes y `Message-ID`.
- `obtener_historial_por_thread(thread_id)`:
  - Trae el historial del hilo en `[Gmail]/All Mail` o `INBOX`, para dar contexto a la IA.
- `crear_borrador(...)`:
  - Crea un borrador en `[Gmail]/Drafts` usando `MIMEText` y `imap.append`.
- `existe_borrador_para_message_id(message_id)`:
  - Revisa si ya existe un borrador asociado al mismo `Message-ID` para evitar duplicados.


Motor de IA (Gemini)
--------------------

En [`kyber/ai.py`](file:///c:/Users/FerneyEnriqueBarbosa/Documents/AgentIA/kyber/ai.py):

- Usa `google.generativeai` con el modelo `gemini-2.5-flash`.
- Construye un prompt muy detallado con:
  - Reglas de negocio (`obtener_reglas`).
  - Plantillas de respuesta (`obtener_respuestas`).
  - Correo recibido (remitente, asunto, cuerpo).
  - Historial reciente del hilo.
- La IA responde en JSON con:

```json
{
  "accion": "BORRADOR" | "NADA",
  "idioma": "es" | "en" | "otro",
  "borrador": "texto del borrador",
  "resumen_es": "resumen en español",
  "plantilla_id": 0,
  "categoria": "COTIZACIONES" | "ANUNCIO" | "GENERAL"
}
```

El servidor valida y normaliza esta respuesta antes de decidir si crear un borrador.


Comandos útiles
---------------

Todos estos comandos se asumen con el entorno virtual activado (`.venv`):

```bash
# Activar entorno virtual (Windows)
.venv\Scripts\Activate.ps1

# Activar entorno virtual (Linux/macOS)
source .venv/bin/activate

# Instalar dependencias principales
pip install fastapi "uvicorn[standard]" starlette jinja2 google-generativeai

# Levantar servidor
uvicorn kyber.web:app --reload
```

Si al ejecutar `python` en Windows ves el mensaje:

> no se encontró Python; ejecutar sin argumentos para instalar desde el Microsoft Store

Significa que no tienes Python correctamente instalado en PATH.  
Instálalo desde https://www.python.org y asegúrate de marcar “Add Python to PATH”.


Estructura básica del proyecto
------------------------------

Resumen de los directorios más relevantes:

- `kyber/`
  - `web.py` — aplicación FastAPI, rutas, panel y lógica de escaneo.
  - `ai.py` — integración con Gemini, prompts y postprocesado de respuestas.
  - `gmail_client.py` — conexión IMAP con Gmail y creación de borradores.
  - `db.py` — acceso a SQLite (usuarios, reglas, respuestas, logs).
  - `settings.py` — carga de variables desde `.env`.
- `templates/`
  - `base.html`, `index.html`, `login.html`, `register.html` — vistas Jinja2.
- `.env` — variables de entorno locales (no se sube a Git).
- `.venv/` — entorno virtual de Python (local).
- `kyber.db` — base de datos SQLite (se crea en tiempo de ejecución).


Buenas prácticas recomendadas
-----------------------------

- Nunca subas `.env`, `.venv` ni `kyber.db` a un repositorio público.
- Cambia periódicamente la contraseña de aplicación de Gmail.
- Usa una API key de Gemini solo para este proyecto y revócala si sospechas de exposición.
- Si llevas el proyecto a producción:
  - Usa un servidor ASGI como `uvicorn` detrás de un proxy inverso (Nginx, Caddy, etc.).
  - Configura HTTPS en el dominio que uses.


Copyright
---------

Copyright © by SHEI (shei.com.co)

