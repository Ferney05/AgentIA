import os
import re
from typing import Dict, List

import google.generativeai as genai

from .db import obtener_reglas, obtener_respuestas


def _configurar_modelo(api_key: str | None = None) -> genai.GenerativeModel:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-2.5-flash")


def _reglas_como_texto() -> str:
    reglas = obtener_reglas()
    items: List[tuple[int, str, str, str]] = []
    for _, clave, instruccion, prioridad, tipo, etiquetas, es_principal in reglas:
        tipo_norm = (tipo or "negocio").lower()
        # Excluir 'firma' del prompt, ya que se agrega programáticamente
        if tipo_norm == "firma":
            continue
        if tipo_norm != "negocio":
            continue
        try:
            prio_val = int(prioridad)
        except Exception:
            prio_val = 3
        linea = f"[PRIORIDAD {prio_val}] {clave}: {instruccion}"
        if (etiquetas or "").strip():
            linea = f"{linea} (Etiquetas: {(etiquetas or '').strip()})"
        etiqueta_orden = (etiquetas or "").strip().lower()
        items.append((prio_val, etiqueta_orden, str(clave), linea))
    # Orden: prioridad ASC (1, 2, 3...), luego etiqueta asc, luego clave asc
    items.sort(key=lambda x: (x[0], x[1], x[2]))
    partes = [linea for _, _, _, linea in items]
    texto = "\n\n".join(partes)
    return texto if texto else "Sin reglas adicionales; usa buen criterio profesional."


def _plantillas_como_texto() -> str:
    plantillas = obtener_respuestas()
    partes: List[str] = []
    for pid, titulo, contenido in plantillas:
        partes.append(f"ID {pid} | TITULO: {titulo}\nTEXTO_COMPLETO:\n{contenido}\n---")
    if not partes:
        return "No hay plantillas configuradas; si no encuentras coincidencia clara, redacta un borrador normal."
    return "\n".join(partes)


def _tareas_politicas_como_texto() -> str:
    reglas = obtener_reglas()
    tareas: List[str] = []
    politicas: List[str] = []
    for _, clave, instruccion, prioridad, tipo, etiquetas, _ in reglas:
        tipo_norm = (tipo or "").lower()
        linea = f"[PRIORIDAD {prioridad}] {clave}: {instruccion}"
        if (etiquetas or "").strip():
            linea = f"{linea} (Etiquetas: {(etiquetas or '').strip()})"
        if tipo_norm == "tarea":
            tareas.append(linea)
        elif tipo_norm == "politica":
            politicas.append(linea)
    bloques: List[str] = []
    if tareas:
        bloques.append("TAREAS ADICIONALES:\n" + "\n".join(tareas))
    if politicas:
        bloques.append("POLITICAS ADICIONALES:\n" + "\n".join(politicas))
    return "\n\n".join(bloques) if bloques else "Sin tareas o políticas adicionales configuradas."


def traducir_texto(texto: str, direccion: str, api_key: str | None = None) -> str:
    modelo = _configurar_modelo(api_key)
    dir_norm = (direccion or "").lower()
    if dir_norm == "es_en":
        instruccion = "Traduce el siguiente texto de español a inglés. Responde solo con la traducción, sin explicaciones ni comentarios adicionales."
    else:
        instruccion = "Traduce el siguiente texto de inglés a español. Responde solo con la traducción, sin explicaciones ni comentarios adicionales."
    prompt = f"{instruccion}\n\n{texto}"
    respuesta = modelo.generate_content(prompt)
    return respuesta.text or ""


def _parse_json(texto: str) -> Dict[str, str]:
    import json

    try:
        return json.loads(texto)
    except Exception:
        pass
    try:
        m = re.search(r"\{[\s\S]*\}", texto)
        if m:
            candidato = m.group(0)
            return json.loads(candidato)
    except Exception:
        pass
    try:
        limpio = texto.strip().replace("“", '"').replace("”", '"').replace("'", '"')
        return json.loads(limpio)
    except Exception:
        return {
            "accion": "NADA",
            "idioma": "desconocido",
            "borrador": "",
            "resumen_es": "No se pudo interpretar la respuesta de la IA.",
            "plantilla_id": 0,
            "categoria": "GENERAL",
        }


def procesar_correo_con_ia(
    remitente: str,
    asunto: str,
    cuerpo: str,
    imagen_mime: str | None = None,
    imagen_datos: bytes | None = None,
    historial_texto: str | None = None,
    api_key: str | None = None,
) -> Dict[str, str]:
    """Procesa un correo electrónico utilizando IA para clasificarlo y generar borradores."""
    modelo = _configurar_modelo(api_key)
    reglas_texto = _reglas_como_texto()
    plantillas_texto = _plantillas_como_texto()
    extras_texto = _tareas_politicas_como_texto()

    cuerpo = re.sub(r'<[^>]+>', '', cuerpo)
    cuerpo = re.sub(r'https?://\S+', '', cuerpo)
    cuerpo = re.sub(r'\s+', ' ', cuerpo).strip()
    # Cortar firmas largas o legales innecesarias para acelerar el análisis
    cuerpo = cuerpo[:2000] # Limitar a 2000 caracteres

    # Prompt optimizado para análisis profundo de repuestos
    prompt = f"""

    Eres KYBER, un agente experto en gestión de bandejas de entrada de Gmail.
    Debes clasificar y redactar borradores siguiendo estrictamente las reglas de negocio del usuario.
    Las REGLAS DE NEGOCIO son SIEMPRE lo más importante: no tomes decisiones por tu cuenta si alguna regla dice lo contrario o limita lo que debes hacer. Si hay duda entre crear borrador o no, elige NO crear borrador ("accion" = "NADA").
    Analiza SIEMPRE todo el contenido disponible: asunto (aunque esté vacío o sea poco claro), texto completo del cuerpo, historial del hilo y, si existe, la IMAGEN adjunta (por ejemplo fotos de la máquina, placa, serial, número de pieza o cotizaciones impresas).

    REGLAS DE NEGOCIO:
    {reglas_texto}

    PLANTILLAS DISPONIBLES (RESPUESTAS PRECONFIGURADAS):
    {plantillas_texto}

    CORREO RECIBIDO:
    - Remitente: {remitente}
    - Asunto: {asunto}
    - Cuerpo:
    {cuerpo}

    HISTORIAL (mensajes recientes en el hilo):
    {historial_texto if historial_texto else "Sin historial disponible"}

    TAREAS:
    1. Detecta el idioma principal del correo.
    2. Clasificación Crítica (ANUNCIO vs COTIZACIÓN):
       - "anuncio": Identifica si el correo es marketing, publicidad, newsletter, promociones masivas, o noticias de la industria. 
         *OJO*: Si el correo tiene un diseño de boletín, muchos enlaces a redes sociales, o lenguaje de "oferta por tiempo limitado", "conoce lo nuevo", "descuentos de temporada", CLASIFÍCALO COMO "ANUNCIO" incluso si menciona repuestos o máquinas.
       - "cotizacion_completa": El cliente pide explícitamente precios o disponibilidad y proporciona datos técnicos (Serial o Part Number).
       - "cotizacion_incompleta": El cliente pide precios pero le falta información crítica (como el Serial).
       - "pregunta_general": Dudas puntuales que no son pedidos de precio ni publicidad.

    3. Detecta si el cliente está pidiendo una cotización y revisa si mencionó explícitamente:
    -MODELO de la máquina o equipo (por ejemplo: "LOADER 544K", "450G", "301.4C", "215", "205"").
    - SERIAL de la máquina o equipo (por ejemplo: "1DW544KZHB0634507").
    - NÚMERO DE PIEZA o PART NUMBER (por ejemplo: "5P-3856", "5V3949", "87682993", "450-6789"). Un número de pieza válido debe tener como mínimo 7 caracteres alfanuméricos (letras y/o números) y puede incluir guion.
    Ten en cuenta que, para el usuario, el SERIAL o el NÚMERO DE PIEZA suelen ser suficientes para poder cotizar aunque falte el modelo; en cambio, tener solo el modelo sin serial ni número de pieza no es suficiente para cotizar.
    3. Determina el tipo de correo incluso si el texto es muy corto, poco claro o sin asunto:
       - "cotizacion_incompleta": el cliente quiere cotización pero NO envía ni serial ni número de pieza.
         * IMPORTANTE: Si menciona MODELO (ej: "312D") y PIEZAS (ej: "cadena", "sprockets", "rodillos"), PERO falta el SERIAL o detalles técnicos (ej: superior/inferior), clasifícalo como "cotizacion_incompleta" y pide esos datos específicos.
       - "cotizacion_completa": el cliente quiere cotización y entrega el serial o un número de pieza válido.
       - "pregunta_general": dudas post-cotización o consultas generales.
       - "anuncio": correos de marketing, publicidad, newsletters.
    4. TAREA PRINCIPAL: ANÁLISIS EXHAUSTIVO Y SELECCIÓN DE PLANTILLAS.
    - ANÁLISIS PROFUNDO: Antes de decidir, LEE Y ANALIZA CUIDADOSAMENTE:
        * El ASUNTO (puede contener la clave, ej: "Pago", "Cotización").
        * El CUERPO COMPLETO (busca la intención real detrás del texto).
        * Los ADJUNTOS (si hay imagen, ¿qué muestra? ¿Un repuesto? ¿Una factura?).
    - COMPARACIÓN OBLIGATORIA: Debes "leer" mentalmente TODAS las plantillas disponibles en la lista de arriba.
    - COINCIDENCIA DE INTENCIÓN: No busques solo palabras exactas. Busca el SIGNIFICADO.
        * Ejemplo: Si el cliente dice "¿A dónde transfiero?", busca plantillas sobre "Métodos de Pago" o "Cuentas Bancarias", aunque no digan la palabra "transfiero".
    - REGLA DE ORO: SI EXISTE UNA PLANTILLA QUE CUBRA LA INTENCIÓN, ÚSALA.
    
    - CÓMO USAR LA PLANTILLA:
        1. Toma el "TEXTO_COMPLETO" de la plantilla seleccionada.
        2. MANEJO DE VARIABLES FALTANTES (CRÍTICO):
           - Si la plantilla pide un dato que NO tienes (ej: {{LINK_PAGO}}, [NUM_FACTURA], [PRECIO]):
           - ¡GENERA EL BORRADOR IGUAL! NO LO DESCARTES.
           - Deja el marcador explícito en el texto (ej: "[INSERTAR_LINK_AQUI]" o mantén el original {{...}}) para que el usuario humano lo rellene después.
           - El usuario sabe que debe poner esos datos manualmente. TU TRABAJO ES PREPARAR EL ESQUELETO DEL CORREO.
        3. Si tienes el dato en el correo del cliente (ej: menciona el modelo), rellénalo.
        4. NO CAMBIES el tono ni la estructura base de la plantilla.
    - EJEMPLO: Si la plantilla dice "Pague aquí: {{LINK}}", y no tienes el link, genera el borrador diciendo "Pague aquí: [INSERTAR_LINK]". NO respondas "NADA".
    
    5. Lógica de decisión (respetando SIEMPRE las reglas de negocio):
    - Si "cotizacion_completa": "accion" = "NADA" (el humano cotiza).
    - Si "cotizacion_incompleta":
        - BUSCA plantilla de "Faltan datos" o "Solicitud de serial".
        - Si la encuentras: "accion" = "BORRADOR", "plantilla_id" = ID, "borrador" = plantilla adaptada.
        - Si NO encuentras plantilla adecuada: "accion" = "NADA" (No inventes nada).
    - Si "anuncio": "accion" = "NADA".
    - Si "pregunta_general":
        - REVISA TODAS LAS PLANTILLAS GENERALES (Pagos, Ubicación, Horarios, etc.).
        - Si alguna coincide con la duda del cliente: "accion" = "BORRADOR", "plantilla_id" = ID, "borrador" = plantilla adaptada.
        - Si NO existe ninguna plantilla relacionada: "accion" = "NADA".

    6. PROHIBIDO REDACTAR DESDE CERO.
    - Si ninguna plantilla encaja con la solicitud del cliente:
        - "accion" = "NADA".
        - "resumen_es": DEBES explicar por qué no se actuó. Ejemplo: "No se encontró plantilla adecuada para solicitud de [INTENCIÓN DETECTADA]. Se requiere revisión manual."
    - Prefiere no responder a inventar una respuesta que no esté homologada en las plantillas.

    7. Asigna también una CATEGORÍA para el log con el campo "categoria":
    - "COTIZACIONES": ÚSALO SOLO si el cliente pide explícitamente PRECIO, DISPONIBILIDAD o PRESUPUESTO.
      * IMPORTANTE: Preguntas breves como "¿Cómo pago?", "¿Dónde están ubicados?", "¿Tienen cuenta bancaria?" SON "GENERAL", NO SON COTIZACIONES. No clasifiques como cotización si no hay intención de compra de repuestos/maquinaria.
    - "ANUNCIO": Para campañas, promociones, newsletters. (Esta categoría sirve para que el sistema ignore el correo automáticamente).
    - "GENERAL": Para todo lo demás (preguntas administrativas, pagos, dudas breves, saludos sin solicitud de precio).
    8. Si el correo está en inglés:
    - Redacta el borrador de respuesta en inglés.
    - Genera un resumen en español del correo recibido.
    9. Si el correo está en español:
    - Redacta el borrador de respuesta en español, a menos que las reglas indiquen otra cosa.
    - Resume el correo en español.
    10. En todos los casos:
    - Responde de forma concreta a lo que pide el cliente.
    - Evita adornos y texto innecesario.
    - No menciones la empresa ni quiénes somos.
    - No añadas firmas, nombres ni datos de contacto al final; el correo ya tiene un pie de página preconfigurado. Limítate al contenido principal del mensaje.  
    
    DEVUELVE SOLO JSON, sin texto extra ni formato, con esta estructura:
    {{
    "accion": "BORRADOR" | "NADA",
    "idioma": "es" | "en" | "otro",
    "borrador": "texto del borrador o vacío si NADA",
    "resumen_es": "resumen breve en español",
    "plantilla_id": 0 | número de plantilla usada si aplica,
    "categoria": "COTIZACIONES" | "ANUNCIO" | "GENERAL"
    }}
    """
    prompt = prompt.replace(
        "7. Asigna también una CATEGORÍA para el log con el campo \"categoria\":",
        f"{extras_texto}\n\n7. Asigna también una CATEGORÍA para el log con el campo \"categoria\":",
    )

    if imagen_mime and imagen_datos:
        respuesta = modelo.generate_content(
            [
                prompt,
                {
                    "mime_type": imagen_mime,
                    "data": imagen_datos,
                },
            ]
        )
    else:
        respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)

    accion = str(datos.get("accion", "NADA")).upper()
    if accion not in {"BORRADOR", "NADA"}:
        accion = "NADA"

    try:
        plantilla_id_val = int(datos.get("plantilla_id", 0))
    except Exception:
        plantilla_id_val = 0
    if plantilla_id_val < 0:
        plantilla_id_val = 0

    categoria_val = str(datos.get("categoria", "") or "").upper()
    if categoria_val not in {"COTIZACIONES", "ANUNCIO", "GENERAL"}:
        categoria_val = ""

    borrador_texto = str(datos.get("borrador", ""))
    if accion == "BORRADOR" and borrador_texto:
        firma = (
            "\n\nFerney Barbosa\n"
            "Desarrollador de software\n"
            "Coordinación de gestión de tecnologías y las comunicaciones\n"
            "Sabanarlarga, Atlántico"
        )
        borrador_texto = f"{borrador_texto.strip()}{firma}"

    resultado: Dict[str, str] = {
        "accion": accion,
        "idioma": str(datos.get("idioma", "desconocido")),
        "borrador": borrador_texto,
        "resumen_es": str(datos.get("resumen_es", "")),
        "plantilla_id": plantilla_id_val,
        "categoria": categoria_val,
    }
    return resultado


def sugerir_clave_prioridad(instruccion: str, api_key: str | None = None) -> Dict[str, str]:
    modelo = _configurar_modelo(api_key)
    guia = """
Eres un asistente que clasifica y titula reglas de educación para un agente de correo.
Objetivo:
- Genera una CLAVE concisa y capitalizada (1–3 palabras, sin guiones ni guiones bajos) que represente la instrucción.
- Asigna una PRIORIDAD del 1 al 5:
  5: política crítica (bloquear borrador, no responder, cotizaciones/presupuesto, cumplimiento estricto)
  4: decisión operativa relevante (filtrar no accionables, spam suave, uso obligado de plantilla)
  3: comportamiento estándar o general (normas por defecto)
  2: ajustes de tono/estilo/idioma/cortesía
  1: sugerencia menor o cosmética
Devuelve SOLO JSON con:
{"clave": "Texto Capitalizado", "prioridad": 1}
"""
    prompt = f"{guia}\n\nINSTRUCCION:\n{instruccion}\n\nJSON:"
    respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)
    clave = str(datos.get("clave", "")).strip()
    try:
        prioridad_val = int(datos.get("prioridad", 3))
    except Exception:
        prioridad_val = 3
    if prioridad_val < 1 or prioridad_val > 5:
        prioridad_val = 3
    if not clave:
        palabras = (instruccion or "").strip().split()
        w1 = palabras[0].capitalize() if palabras else "General"
        w2 = palabras[1].lower() if len(palabras) > 1 else ""
        clave = f"{w1} {w2}".strip() if w2 else w1
    _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"
    return {"clave": clave, "prioridad": str(prioridad_val)}


def sugerir_etiquetas(instruccion: str, api_key: str | None = None) -> Dict[str, str]:
    modelo = _configurar_modelo(api_key)
    guia = """
Genera etiquetas cortas y en minúsculas, separadas por comas, basadas en la instrucción.
Reglas:
- 1 a 5 etiquetas máximo.
- Evita duplicados y palabras vacías.
- Usa términos comunes del dominio: cotizaciones, serial, modelo, pieza, idioma, ingles, español, anuncio, spam, plantillas, borrador, seguimiento, general.
Devuelve SOLO JSON:
{"etiquetas": "tag1, tag2"}
"""
    prompt = f"{guia}\n\nINSTRUCCION:\n{instruccion}\n\nJSON:"
    respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)
    etiquetas_raw = str(datos.get("etiquetas", "")).strip()
    if not etiquetas_raw:
        base = (instruccion or "").lower()
        sugeridas = []
        if any(k in base for k in ["cotiz", "presup", "precio"]):
            sugeridas.append("cotizaciones")
        if "serial" in base or "serie" in base:
            sugeridas.append("serial")
        if "modelo" in base:
            sugeridas.append("modelo")
        if "pieza" in base or "part number" in base or "repuesto" in base:
            sugeridas.append("pieza")
        if "inglés" in base or "english" in base:
            sugeridas.append("ingles")
        if "español" in base or "spanish" in base:
            sugeridas.append("español")
        if any(k in base for k in ["promoc", "descuento", "newsletter", "campaña"]):
            sugeridas.append("anuncio")
        if "plantilla" in base:
            sugeridas.append("plantillas")
        etiquetas_raw = ", ".join(dict.fromkeys(sugeridas))  # elimina duplicados conservando orden
    return {"etiquetas": etiquetas_raw}
