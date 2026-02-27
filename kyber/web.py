from datetime import datetime, timedelta
import hashlib
import os
import re

from fastapi import FastAPI, Form, Request, Query, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .settings import cargar_env

cargar_env()

from .ai import procesar_correo_con_ia
from .ai import sugerir_clave_prioridad
from .ai import traducir_texto
from .ai import sugerir_etiquetas
from .db import (
    crear_base_de_datos,
    insertar_log,
    insertar_regla,
    obtener_reglas,
    obtener_resumen_logs,
    obtener_ultimos_logs,
    obtener_regla_por_id,
    actualizar_regla,
    eliminar_regla,
    insertar_respuesta,
    obtener_respuestas,
    obtener_respuesta_por_id,
    actualizar_respuesta,
    eliminar_respuesta,
    crear_usuario,
    obtener_usuario_por_email,
    obtener_usuario_por_id,
    obtener_logs_filtrados_paginados,
    eliminar_logs,
)
from .gmail_client import (
    crear_borrador,
    obtener_ids_no_leidos,
    obtener_correos_por_ids,
    marcar_como_leido,
    marcar_como_no_leido,
    obtener_historial_por_thread,
    existe_borrador_para_message_id,
    existe_borrador_para_thread_id,
)


app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("KYBER_SESSION_SECRET", "kyber-dev-session-secret"),
)
templates = Jinja2Templates(directory="templates")
AGENTE_ACTIVO = False


def _hash_password(raw: str) -> str:
    base = f"kyber-salt::{raw}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _verify_password(raw: str, hashed: str) -> bool:
    return _hash_password(raw) == hashed


def _get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return obtener_usuario_por_id(int(user_id))


def _user_info(usuario):
    if not usuario:
        return None
    _id, email, _ph, _creado, gemini_key, gmail_user, gmail_pwd, batch, max_scan, activo = usuario
    username = email.split("@")[0] if "@" in email else email
    username = username.strip() or email
    initial = username[0].upper()
    return {
        "id": _id, 
        "email": email, 
        "username": username, 
        "initial": initial,
        "gemini_api_key": gemini_key,
        "gmail_user": gmail_user,
        "gmail_password": gmail_pwd,
        "scan_batch": batch or 10,
        "scan_max": max_scan or 100,
        "agente_activo": bool(activo)
    }


@app.on_event("startup")
def startup() -> None:
    crear_base_de_datos()


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    toast: str | None = Query(default=None),
    edit_id: int | None = Query(default=None),
    view: str | None = Query(default="dashboard"),
    edit_respuesta_id: int | None = Query(default=None),
    periodo: str | None = Query(default="diario"),
    page: int | None = Query(default=1),
    filtro_categoria: str | None = Query(default=None),
    filtro_accion: str | None = Query(default=None),
) -> HTMLResponse:
    usuario = _get_current_user(request)
    if not usuario:
        return RedirectResponse(url="/auth/login", status_code=303)
    user_info = _user_info(usuario)

    stats = obtener_resumen_logs(usuario_id=user_info["id"])
    reglas = obtener_reglas(usuario_id=user_info["id"])
    page_size = 20
    try:
        page_val = int(page or 1)
    except Exception:
        page_val = 1
    if page_val < 1:
        page_val = 1

    cat = (filtro_categoria or "").strip().upper() or None
    if cat not in {None, "GENERAL", "COTIZACIONES", "ANUNCIO"}:
        cat = None
    acc = (filtro_accion or "").strip().upper() or None

    offset = (page_val - 1) * page_size
    logs_raw, total_logs = obtener_logs_filtrados_paginados(
        limite=page_size,
        offset=offset,
        usuario_id=user_info["id"],
        categoria=cat,
        accion=acc,
    )
    logs = []
    for fila in logs_raw:
        try:
            dt = datetime.fromisoformat(fila[0])
            fecha_fmt = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            fecha_fmt = fila[0]
        logs.append(
            (fecha_fmt, fila[1], fila[2], fila[3], fila[4], fila[5], fila[6])
        )
    regla_editar = obtener_regla_por_id(edit_id) if edit_id is not None else None
    respuestas = obtener_respuestas(usuario_id=user_info["id"])
    try:
        per = (periodo or "diario").lower()
        if per not in {"diario", "semanal", "mensual"}:
            per = "diario"
    except Exception:
        per = "diario"
    from .db import obtener_borradores_por_periodo
    borradores_periodo = obtener_borradores_por_periodo(periodo=per, usuario_id=user_info["id"])
    respuesta_editar = obtener_respuesta_por_id(edit_respuesta_id) if edit_respuesta_id is not None else None
    total_pages = (total_logs // page_size) + (1 if total_logs % page_size else 0)
    has_prev = page_val > 1
    has_next = page_val < total_pages

    contexto = {
        "request": request,
        "stats": stats,
        "reglas": reglas,
        "logs": logs,
        "toast": toast,
        "regla_editar": regla_editar,
        "respuestas": respuestas,
        "respuesta_editar": respuesta_editar,
        "view": view,
        "user": user_info,
        "borradores_periodo": borradores_periodo,
        "periodo": per,
        "page": page_val,
        "page_size": page_size,
        "total_logs": total_logs,
        "has_prev": has_prev,
        "has_next": has_next,
        "filtro_categoria": cat,
        "filtro_accion": acc,
    }
    return templates.TemplateResponse("index.html", contexto)


def _normalizar_token(texto: str, default: str = "General") -> str:
    t = (texto or "").strip()
    if not t:
        return default
    partes = re.split(r"[^0-9A-Za-zÁÉÍÓÚÑáéíóúñ]+", t)
    partes = [p for p in partes if p]
    if not partes:
        return default
    w = partes[0].lower()
    return w[:1].upper() + w[1:] if w else default


def _auto_clave(desde_instruccion: str) -> str:
    texto = (desde_instruccion or "").strip()
    texto = " ".join(texto.split())
    if not texto:
        return "General"
    return _normalizar_token(texto, default="General")

def _inferir_prioridad(texto: str) -> int:
    t = (texto or "").lower()
    kw5 = ["cotiz", "presupuesto", "quote", "quotation", "pricing", "estimate", "no redact", "no respond", "bloquear borrador", "no crear borrador", "crítica"]
    if any(k in t for k in kw5):
        return 5
    kw4 = ["no accionable", "spam", "plantilla obligatoria", "usar plantilla", "usar respuesta"]
    if any(k in t for k in kw4):
        return 4
    kw2 = ["tono", "estilo", "formal", "cortesía", "idioma"]
    if any(k in t for k in kw2):
        return 2
    return 3


@app.post("/learn")
def learn(
    request: Request,
    instruccion: str = Form(...),
    clave: str | None = Form(default=None),
    prioridad: str = Form(default="auto"),
    tipo: str = Form(default="negocio"),
    etiquetas: str = Form(default=""),
    regla_id: int | None = Form(default=None),
) -> RedirectResponse:
    usuario = _get_current_user(request)
    if not usuario:
        return RedirectResponse(url="/auth/login", status_code=303)
    user_info = _user_info(usuario)

    clave_final = clave.strip() if clave else ""
    if not clave_final:
        return RedirectResponse(url="/?view=rules&toast=error_clave_requerida", status_code=303)
    
    # Capitalizar la primera letra de la frase completa
    clave_final = clave_final[0].upper() + clave_final[1:] if clave_final else "Regla"

    prioridad_sugerida_por_ia: int | None = None

    def _inferir_prioridad(texto: str) -> int:
        t = (texto or "").lower()
        kw5 = ["cotiz", "presupuesto", "quote", "quotation", "pricing", "estimate", "no redact", "no respond", "bloquear borrador", "no crear borrador", "crítica"]
        if any(k in t for k in kw5):
            return 5
        kw4 = ["archivar", "no accionable", "spam", "plantilla obligatoria", "usar plantilla", "usar respuesta"]
        if any(k in t for k in kw4):
            return 4
        kw2 = ["tono", "estilo", "formal", "cortesía", "idioma"]
        if any(k in t for k in kw2):
            return 2
        return 3

    try:
        prioridad_int = int(prioridad)
    except Exception:
        prioridad_int = _inferir_prioridad(instruccion)
    if prioridad_sugerida_por_ia and (prioridad or "auto").strip().lower() == "auto":
        if 1 <= prioridad_sugerida_por_ia <= 5:
            prioridad_int = prioridad_sugerida_por_ia

    tipo_norm = (tipo or "negocio").strip().lower()
    if tipo_norm not in {"negocio", "tarea", "politica"}:
        tipo_norm = "negocio"
    etiquetas_txt = (etiquetas or "").strip()
    if not etiquetas_txt:
        try:
            sugeridas = sugerir_etiquetas(instruccion).get("etiquetas", "").strip()
        except Exception:
            sugeridas = ""
        if sugeridas:
            primera = [t.strip().lower() for t in sugeridas.split(",") if t.strip()][0] if [t.strip() for t in sugeridas.split(",") if t.strip()] else ""
            etiquetas_txt = primera or ""
        if not etiquetas_txt:
            if prioridad_int == 5:
                etiquetas_txt = "cotizaciones"
            elif prioridad_int == 4:
                etiquetas_txt = "operativa"
            elif prioridad_int == 2:
                etiquetas_txt = "tono"
            else:
                etiquetas_txt = "general"
    etiquetas_txt = _normalizar_token(etiquetas_txt, default="General")
    if regla_id is not None:
        actualizar_regla(regla_id, clave_final, instruccion, prioridad=prioridad_int, tipo=tipo_norm, etiquetas=etiquetas_txt, es_principal=0)
        destino = "/?view=rules&toast=regla_editada"
    else:
        insertar_regla(clave_final, instruccion, usuario_id=user_info["id"], prioridad=prioridad_int, tipo=tipo_norm, etiquetas=etiquetas_txt, es_principal=0)
        destino = "/?view=rules&toast=regla_creada"

    return RedirectResponse(url=destino, status_code=303)


@app.post("/rules/suggest")
def rules_suggest(
    request: Request,
    instruccion: str = Form(...),
) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"error": "unauthorized"}
    try:
        sug = sugerir_clave_prioridad(instruccion)
        clave_sug = _normalizar_token(sug.get("clave", ""), default="General")
        return {"ok": True, "clave": clave_sug, "prioridad": sug.get("prioridad", "3")}
    except Exception:
        return {"ok": True, "clave": _auto_clave(instruccion), "prioridad": str(_inferir_prioridad(instruccion))}

@app.post("/rules/tags_suggest")
def rules_tags_suggest(
    request: Request,
    instruccion: str = Form(...),
) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"ok": False, "error": "unauthorized"}
    base = (instruccion or "").lower()
    etiquetas = []
    if any(k in base for k in ["cotiz", "presup", "precio"]):
        etiquetas.append("cotizaciones")
    if "serial" in base or "serie" in base:
        etiquetas.append("serial")
    if "modelo" in base:
        etiquetas.append("modelo")
    if "pieza" in base or "part number" in base or "repuesto" in base:
        etiquetas.append("pieza")
    if "inglés" in base or "english" in base:
        etiquetas.append("ingles")
    if "español" in base or "spanish" in base:
        etiquetas.append("español")
    if any(k in base for k in ["promoc", "descuento", "newsletter", "campaña"]):
        etiquetas.append("anuncio")
    if "plantilla" in base:
        etiquetas.append("plantillas")
    uniq = list(dict.fromkeys(etiquetas))
    etiqueta = uniq[0] if uniq else ""
    etiqueta_norm = _normalizar_token(etiqueta, default="")
    return {"ok": True, "etiqueta": etiqueta_norm}
@app.post("/respuestas")
def crear_actualizar_respuesta(
    request: Request,
    titulo: str = Form(...),
    contenido: str = Form(...),
    respuesta_id: int | None = Form(default=None),
) -> RedirectResponse:
    usuario = _get_current_user(request)
    if not usuario:
        return RedirectResponse(url="/auth/login", status_code=303)
    user_info = _user_info(usuario)
    if respuesta_id is not None:
        actualizar_respuesta(respuesta_id, titulo, contenido)
        destino = "/?view=respuestas&toast=respuesta_editada"
    else:
        insertar_respuesta(titulo, contenido, usuario_id=user_info["id"])
        destino = "/?view=respuestas&toast=respuesta_creada"
    return RedirectResponse(url=destino, status_code=303)

@app.post("/respuestas/{respuesta_id}/delete")
def eliminar_respuesta_endpoint(respuesta_id: int = Path(...)) -> RedirectResponse:
    eliminar_respuesta(respuesta_id)
    return RedirectResponse(url="/?view=respuestas&toast=respuesta_eliminada", status_code=303)

@app.post("/rules/{regla_id}/delete")
def delete_rule(regla_id: int = Path(...)) -> RedirectResponse:
    eliminar_regla(regla_id)
    return RedirectResponse(url="/?view=rules&toast=regla_eliminada", status_code=303)


def _ejecutar_scan(user_info: dict) -> int:
    ahora_dt = datetime.utcnow()
    ahora = ahora_dt.isoformat()
    
    # Lógica de fecha para el escaneo:
    # Si es Lunes (weekday == 0), buscamos desde el Sábado (2 días atrás)
    # Si es cualquier otro día, buscamos solo desde hoy.
    dias_atras = 0
    if ahora_dt.weekday() == 0:  # Lunes
        dias_atras = 2
    
    fecha_inicio = ahora_dt - timedelta(days=dias_atras)
    # Formato IMAP: "DD-Mon-YYYY" (ej: "27-Feb-2026")
    meses_eng = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    desde_fecha_imap = f"{fecha_inicio.day}-{meses_eng[fecha_inicio.month-1]}-{fecha_inicio.year}"

    batch = user_info.get("scan_batch", 10)
    max_total = user_info.get("scan_max", 100)
    api_key = user_info.get("gemini_api_key")
    gmail_user = user_info.get("gmail_user")
    gmail_pwd = user_info.get("gmail_password")

    if not api_key or not gmail_user or not gmail_pwd:
        return 0

    ids = obtener_ids_no_leidos(max_total, usuario=gmail_user, clave_app=gmail_pwd, desde_fecha=desde_fecha_imap)

    total = 0
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        correos = obtener_correos_por_ids(chunk, usuario=gmail_user, clave_app=gmail_pwd)

        ids_para_marcar: list[str] = []
        ids_para_no_leer: list[str] = []

        for correo in correos:
            historial_texto = ""
            thr = correo.get("thread_id")
            mensaje_id = correo.get("message_id") or ""
            if thr and existe_borrador_para_thread_id(thr, usuario=gmail_user, clave_app=gmail_pwd):
                insertar_log(
                    fecha=ahora,
                    remitente=correo["remitente"],
                    asunto=correo["asunto"],
                    resumen=f"Hilo omitido por borrador previo (thread_id={thr})",
                    accion="OMITIDO_BORRADOR_THREAD",
                    idioma="desconocido",
                    categoria="GENERAL",
                    usuario_id=user_info["id"]
                )
                ids_para_no_leer.append(correo["id"])
                continue
            if mensaje_id and existe_borrador_para_message_id(mensaje_id, usuario=gmail_user, clave_app=gmail_pwd):
                insertar_log(
                    fecha=ahora,
                    remitente=correo["remitente"],
                    asunto=correo["asunto"],
                    resumen=f"Mensaje omitido por borrador previo (Message-ID={mensaje_id})",
                    accion="OMITIDO_BORRADOR_MSG",
                    idioma="desconocido",
                    categoria="GENERAL",
                    usuario_id=user_info["id"]
                )
                ids_para_no_leer.append(correo["id"])
                continue
            ultimo_de_mi_usuario = False
            if thr:
                hist = obtener_historial_por_thread(thr, limite=5, usuario=gmail_user, clave_app=gmail_pwd)
                if hist:
                    my_email = (gmail_user or "").lower()
                    try:
                        ultimo = hist[-1]
                        ultimo_from = (ultimo.get("from") or "").lower()
                        if my_email and my_email in ultimo_from:
                            ultimo_de_mi_usuario = True
                    except Exception:
                        ultimo_de_mi_usuario = False
                    partes = []
                    for h in hist:
                        partes.append(f"- {h.get('from','')} · {h.get('subject','')}: {h.get('body','')}")
                    historial_texto = "\n".join(partes)
            if ultimo_de_mi_usuario:
                ids_para_no_leer.append(correo["id"])
                continue
            
            resultado = procesar_correo_con_ia(
                remitente=correo["remitente"],
                asunto=correo["asunto"],
                cuerpo=correo["cuerpo"],
                imagen_mime=correo.get("imagen_mime"),
                imagen_datos=correo.get("imagen_datos"),
                historial_texto=historial_texto,
                api_key=api_key
            )

            asunto_min = (correo["asunto"] or "").lower()
            cuerpo_min = (correo["cuerpo"] or "").lower()
            tiene_imagen = bool(correo.get("imagen_mime") and correo.get("imagen_datos"))
            asunto_u = (correo["asunto"] or "").upper()
            cuerpo_u = (correo["cuerpo"] or "").upper()

            categoria = (resultado.get("categoria") or "").upper()
            palabras_cot = (
                "cotiz" in asunto_min
                or "cotiz" in cuerpo_min
                or "cotizar" in asunto_min
                or "cotizar" in cuerpo_min
                or "presupuesto" in asunto_min
                or "presupuesto" in cuerpo_min
                or "quote" in asunto_min
                or "quote" in cuerpo_min
                or "quotation" in asunto_min
                or "quotation" in cuerpo_min
                or "pricing" in asunto_min
                or "pricing" in cuerpo_min
                or "estimate" in asunto_min
                or "estimate" in cuerpo_min
                or "precio" in asunto_min
                or "precio" in cuerpo_min
            )
            marcas = ["caterpillar", "cat", "john deere", "komatsu", "hitachi", "volvo", "case", "tcm"]
            menciona_marca = any(m in asunto_min or m in cuerpo_min for m in marcas)
            modelo_pat1 = r"\b\d{2,4}[A-Z]\b"
            modelo_pat2 = r"\b[A-Z]{3,}\s?\d{2,4}[A-Z]?\b"
            posible_modelo = bool(
                re.search(modelo_pat1, asunto_u) or re.search(modelo_pat1, cuerpo_u) or
                re.search(modelo_pat2, asunto_u) or re.search(modelo_pat2, cuerpo_u)
            )
            pn_hyphen = bool(re.search(r"\b[0-9A-Z]{1,5}-[0-9A-Z]{3,}\b", asunto_u) or re.search(r"\b[0-9A-Z]{1,5}-[0-9A-Z]{3,}\b", cuerpo_u))
            pn_plain = bool(re.search(r"\b[0-9A-Z]{7,}\b", asunto_u) or re.search(r"\b[0-9A-Z]{7,}\b", cuerpo_u))
            tiene_pn = pn_hyphen or pn_plain
            tiene_serial = bool(re.search(r"\b[0-9A-Z\-]{10,}\b", asunto_u) or re.search(r"\b[0-9A-Z\-]{10,}\b", cuerpo_u))
            es_cotizacion = (
                categoria == "COTIZACIONES"
                or palabras_cot
                or (tiene_imagen and ("cotiz" in cuerpo_min or "precio" in cuerpo_min))
                or (menciona_marca and posible_modelo)
                or ("favor" in asunto_min and posible_modelo)
            )
            if es_cotizacion:
                categoria = "COTIZACIONES"
                ids_para_no_leer.append(correo["id"])
                if resultado.get("accion") != "BORRADOR" and not (tiene_pn or tiene_serial) and (posible_modelo or tiene_imagen or menciona_marca):
                    resultado["accion"] = "BORRADOR"
                    resultado["borrador"] = "Muy buenas tardes Estimad@,\nPara cotizarle, por favor envíe el serial o número de pieza de la máquina."
            elif categoria == "ANUNCIO":
                resultado["accion"] = "NADA"
                resultado["borrador"] = ""
                ids_para_no_leer.append(correo["id"])


            if resultado["accion"] == "BORRADOR":
                if thr and existe_borrador_para_thread_id(thr, usuario=gmail_user, clave_app=gmail_pwd):
                    insertar_log(
                        fecha=ahora,
                        remitente=correo["remitente"],
                        asunto=correo["asunto"],
                        resumen=f"Hilo con borrador previo detectado al crear borrador (thread_id={thr})",
                        accion="OMITIDO_BORRADOR_THREAD",
                        idioma=resultado.get("idioma", "desconocido"),
                        categoria=categoria or "GENERAL",
                    )
                    resultado["accion"] = "NADA"
                elif existe_borrador_para_message_id(correo.get("message_id") or "", usuario=gmail_user, clave_app=gmail_pwd):
                    insertar_log(
                        fecha=ahora,
                        remitente=correo["remitente"],
                        asunto=correo["asunto"],
                        resumen=f"Mensaje con borrador previo detectado al crear borrador (Message-ID={correo.get('message_id') or ''})",
                        accion="OMITIDO_BORRADOR_MSG",
                        idioma=resultado.get("idioma", "desconocido"),
                        categoria=categoria or "GENERAL",
                    )
                    resultado["accion"] = "NADA"
                else:
                    def _sanear_borrador(texto: str) -> str:
                        t = (texto or "").strip()
                        empresa = (os.environ.get("KYBER_COMPANY_NAME") or "Mosaic Machines").strip()
                        if empresa:
                            t = re.sub(rf"\b{re.escape(empresa)}\b", "", t, flags=re.IGNORECASE)
                        t = re.sub(r"\b(somos|empresa|proveedores|integrales|estamos listos)\b.*", "", t, flags=re.IGNORECASE)
                        t = re.sub(r"\s+", " ", t).strip()
                        frases = re.split(r"(?<=[.!?])\s+", t)
                        if len(frases) > 2:
                            t = " ".join(frases[:2]).strip()
                        return t
                    plantilla_id = 0
                    try:
                        plantilla_id = int(resultado.get("plantilla_id") or 0)
                    except Exception:
                        plantilla_id = 0
                    if plantilla_id:
                        plantilla = obtener_respuesta_por_id(plantilla_id)
                        if plantilla:
                            resultado["borrador"] = plantilla[2]
                    else:
                        resultado["borrador"] = _sanear_borrador(resultado["borrador"])
                    crear_borrador(
                        responder_a=correo.get("from_email") or correo["remitente"],
                        asunto=f"Re: {correo['asunto']}",
                        cuerpo=resultado["borrador"],
                        in_reply_to=correo.get("message_id"),
                        references=correo.get("message_id"),
                        usuario=gmail_user,
                        clave_app=gmail_pwd
                    )
                    if not es_cotizacion:
                        ids_para_marcar.append(correo["id"])

            insertar_log(
                fecha=ahora,
                remitente=correo["remitente"],
                asunto=correo["asunto"],
                resumen=resultado["resumen_es"],
                accion=resultado["accion"],
                idioma=resultado["idioma"],
                categoria=categoria,
                usuario_id=user_info["id"]
            )
            total += 1

        if ids_para_marcar:
            marcar_como_leido(ids_para_marcar, usuario=gmail_user, clave_app=gmail_pwd)
        if ids_para_no_leer:
            marcar_como_no_leido(ids_para_no_leer, usuario=gmail_user, clave_app=gmail_pwd)

    return total


@app.post("/scan")
def scan(request: Request) -> RedirectResponse:
    usuario = _get_current_user(request)
    if not usuario:
        return RedirectResponse(url="/auth/login", status_code=303)
    user_info = _user_info(usuario)
    _ejecutar_scan(user_info)
    return RedirectResponse(url="/?toast=scan_ok", status_code=303)


@app.get("/agent/status")
def agent_status(request: Request) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"running": False}
    user_info = _user_info(usuario)
    return {"running": user_info["agente_activo"]}


@app.post("/agent/toggle")
def agent_toggle(request: Request) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"error": "unauthorized"}
    user_info = _user_info(usuario)
    nuevo_estado = not user_info["agente_activo"]
    from .db import actualizar_configuracion_usuario
    actualizar_configuracion_usuario(user_info["id"], agente_activo=int(nuevo_estado))
    return {"running": nuevo_estado}


@app.post("/scan-json")
def scan_json(request: Request) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"processed": 0, "running": False}
    user_info = _user_info(usuario)
    if not user_info["agente_activo"]:
        return {"processed": 0, "running": False}
    procesados = _ejecutar_scan(user_info)
    return {"processed": procesados, "running": True}


@app.post("/settings/update")
def settings_update(
    request: Request,
    gemini_api_key: str | None = Form(default=None),
    gmail_user: str | None = Form(default=None),
    gmail_password: str | None = Form(default=None),
    scan_batch: int = Form(default=10),
    scan_max: int = Form(default=100),
) -> RedirectResponse:
    usuario = _get_current_user(request)
    if not usuario:
        return RedirectResponse(url="/auth/login", status_code=303)
    user_info = _user_info(usuario)
    
    from .db import actualizar_configuracion_usuario
    actualizar_configuracion_usuario(
        user_info["id"],
        gemini_api_key=gemini_api_key,
        gmail_user=gmail_user,
        gmail_password=gmail_password,
        scan_batch=scan_batch,
        scan_max=scan_max
    )
    return RedirectResponse(url="/?view=settings&toast=config_actualizada", status_code=303)


@app.post("/translate-json")
def translate_json(
    request: Request,
    texto: str = Form(...),
    direccion: str = Form(default="en_es"),
) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"ok": False, "error": "unauthorized"}
    try:
        traducido = traducir_texto(texto, direccion)
        return {"ok": True, "translated": traducido}
    except Exception:
        return {"ok": False, "error": "error"}


@app.post("/logs/clear-json")
def logs_clear_json(
    request: Request,
    scope: str = Form(default="filtered"),
    filtro_categoria: str | None = Form(default=None),
    filtro_accion: str | None = Form(default=None),
) -> dict:
    usuario = _get_current_user(request)
    if not usuario:
        return {"ok": False, "error": "unauthorized"}
    user_info = _user_info(usuario)
    cat = (filtro_categoria or "").strip().upper() or None
    if cat not in {None, "GENERAL", "COTIZACIONES", "ANUNCIO"}:
        cat = None
    acc = (filtro_accion or "").strip().upper() or None

    categoria = cat
    accion = acc
    if scope == "all":
        categoria = None
        accion = None
    try:
        eliminados = eliminar_logs(
            usuario_id=user_info["id"],
            categoria=categoria,
            accion=accion,
        )
        return {"ok": True, "deleted": eliminados}
    except Exception:
        return {"ok": False, "error": "error"}


@app.get("/auth/login", response_class=HTMLResponse)
def login_get(
    request: Request,
    error: str | None = Query(default=None),
) -> HTMLResponse:
    usuario = _get_current_user(request)
    if usuario:
        return RedirectResponse(url="/", status_code=303)
    contexto = {
        "request": request,
        "error": error,
    }
    return templates.TemplateResponse("login.html", contexto)


@app.post("/auth/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    usuario = obtener_usuario_por_email(email.strip().lower())
    if not usuario:
        return RedirectResponse(url="/auth/login?error=credenciales", status_code=303)
    _id, _email, password_hash, _creado = usuario
    if not _verify_password(password, password_hash):
        return RedirectResponse(url="/auth/login?error=credenciales", status_code=303)

    request.session["user_id"] = _id
    return RedirectResponse(url="/", status_code=303)


@app.get("/auth/register", response_class=HTMLResponse)
def register_get(
    request: Request,
    error: str | None = Query(default=None),
) -> HTMLResponse:
    usuario = _get_current_user(request)
    if usuario:
        return RedirectResponse(url="/", status_code=303)
    contexto = {
        "request": request,
        "error": error,
    }
    return templates.TemplateResponse("register.html", contexto)


@app.post("/auth/register")
def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    email_norm = email.strip().lower()
    if not email_norm or not password:
        return RedirectResponse(url="/auth/register?error=datos", status_code=303)

    existente = obtener_usuario_por_email(email_norm)
    if existente:
        return RedirectResponse(url="/auth/login?error=ya_registrado", status_code=303)

    ahora = datetime.utcnow().isoformat()
    password_hash = _hash_password(password)
    user_id = crear_usuario(email_norm, password_hash, ahora)
    request.session["user_id"] = user_id
    return RedirectResponse(url="/", status_code=303)


@app.post("/auth/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"
    return RedirectResponse(url="/auth/login", status_code=303)
