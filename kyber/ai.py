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
    # Orden: prioridad desc, luego etiqueta asc, luego clave asc
    items.sort(key=lambda x: (-x[0], x[1], x[2]))
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
    modelo = _configurar_modelo(api_key)
    reglas_texto = _reglas_como_texto()
    plantillas_texto = _plantillas_como_texto()
    extras_texto = _tareas_politicas_como_texto()

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
    2. Detecta si el cliente está pidiendo una cotización y revisa si mencionó explícitamente:
    -MODELO de la máquina o equipo (por ejemplo: "LOADER 544K", "450G", "301.4C", "215", "205"").
    - SERIAL de la máquina o equipo (por ejemplo: "1DW544KZHB0634507").
    - NÚMERO DE PIEZA o PART NUMBER (por ejemplo: "5P-3856", "5V3949", "87682993", "450-6789"). Un número de pieza válido debe tener como mínimo 7 caracteres alfanuméricos (letras y/o números) y puede incluir guion.
    Ten en cuenta que, para el usuario, el SERIAL o el NÚMERO DE PIEZA suelen ser suficientes para poder cotizar aunque falte el modelo; en cambio, tener solo el modelo sin serial ni número de pieza no es suficiente para cotizar.
    3. Determina el tipo de correo incluso si el texto es muy corto, poco claro o sin asunto:
    - "cotizacion_incompleta": el cliente quiere una cotización pero NO envía ni serial ni número de pieza (puede que envíe solo modelo, solo nombre del producto, solo una referencia parcial o solo una foto) o falta otra información crítica sin la cual no se pueda cotizar.
    - "cotizacion_completa": el cliente quiere una cotización y entrega el serial o un número de pieza (y opcionalmente el modelo) o suficiente información técnica para cotizar sin pedir más datos. No necesitas que el correo diga literalmente "cotizar": basta con que aparezcan modelo/serial/part number de forma que sea evidente que pide precio o repuestos.
    - "pregunta_general": dudas o preguntas después de que ya se envió una cotización, o consultas generales sobre productos, disponibilidad, tiempos, etc.
    - "anuncio": correos de marketing, publicidad, newsletters, nuevas temporadas, promociones, descuentos, lanzamientos, etc.
    4. Antes de redactar nada, revisa si alguna PLANTILLA se ajusta claramente a la petición del cliente.
    - Analiza tanto el TITULO como el TEXTO_COMPLETO de cada plantilla y compáralos con el asunto, el cuerpo y el historial del hilo. Elige solo la plantilla cuya intención coincida claramente con la pregunta del cliente. Si no hay coincidencia clara o tienes duda, no uses ninguna plantilla y deja "plantilla_id" = 0.
    - Si el correo es una cotización INCOMPLETA y el cliente NO envió ni serial ni número de pieza (puede que tampoco envíe modelo, incluso si la información solo aparece en una imagen adjunta):
        - Si existe una plantilla cuyo propósito sea pedir datos mínimos para cotizar (por ejemplo, “Favor enviar el modelo y serial de la máquina para cotizar…”), úsala tal cual:
        - "accion" = "BORRADOR".
        - "plantilla_id" = ID de esa plantilla.
        - Copia el TEXTO_COMPLETO de esa plantilla directamente en "borrador", sin cambiar ni añadir nada.
    - Si el correo es una cotización INCOMPLETA y el cliente envió modelo pero no serial ni número de pieza (aunque el modelo solo se vea en una imagen):
        - Puedes usar la plantilla como referencia de estilo, pero en ese caso NO debes usar "plantilla_id". En lugar de eso:
        - "plantilla_id" = 0.
        - Redacta un borrador muy corto (1–2 frases máximo) que pida solo el serial que falta, adaptando el estilo de la plantilla y sin añadir explicaciones largas ni contenido que no sea necesario.
    - Si el cliente envía serial (aunque falte modelo), trátalo como "cotizacion_completa" y no pidas más datos; no crees borrador solo para solicitar modelo.
    - Para otras situaciones donde una PLANTILLA coincida exactamente con la pregunta (por ejemplo, explicar original vs reemplazo):
        - "accion" = "BORRADOR".
        - "plantilla_id" = ID numérico de esa plantilla.
        - Copia el TEXTO_COMPLETO de esa plantilla en "borrador", sin modificar nada.
    - No expliques quién es la empresa ni añadas textos comerciales o de presentación.
    5. Lógica según tipo de correo (respetando SIEMPRE las reglas de negocio; si alguna regla indica no crear borrador para cierto caso, obedece esa regla y no crees borrador aunque el correo parezca importante):
    - Si "cotizacion_completa": "accion" = "NADA" y "borrador" vacío. El usuario enviará la cotización en su propio formato.
    - Si "cotizacion_incompleta":
        - Si no hay plantilla adecuada o no es claro qué falta, "accion" = "NADA" y "borrador" vacío.
        - Si hay plantilla clara o puedes redactar un mensaje corto y preciso pidiendo exactamente el dato que falta (normalmente el serial), "accion" = "BORRADOR" y "borrador" contiene solo ese pedido de información adicional.
    - Si "anuncio": "accion" = "NADA" y "borrador" vacío. Son campañas, promociones o newsletters, no requieren respuesta.
    - Si "pregunta_general": responde normalmente siguiendo reglas y plantillas, pero mantén siempre el borrador CORTO (máximo 2–3 frases), directo y sin texto innecesario.
    6. Si ninguna plantilla coincide claramente:
    - Si es un anuncio, spam suave o comunicación no accionable: "accion" = "NADA" y "borrador" vacío.
    - Si requiere respuesta o seguimiento: "accion" = "BORRADOR" y redacta un borrador MUY BREVE (máximo 1–2 frases), directo y sin presentaciones. No menciones la empresa ni escribas textos comerciales.
    7. Asigna también una CATEGORÍA para el log con el campo "categoria":
    - Usa "COTIZACIONES" para cualquier solicitud de precios, cotizaciones o presupuestos (completas o incompletas).
    - Usa "ANUNCIO" para campañas, promociones, newsletters, avisos de temporada, etc.
    - Usa "GENERAL" para el resto de correos.
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

    resultado: Dict[str, str] = {
        "accion": accion,
        "idioma": str(datos.get("idioma", "desconocido")),
        "borrador": str(datos.get("borrador", "")),
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
