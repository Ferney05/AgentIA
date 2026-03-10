# 🎯 Cómo Funciona Inbox Zero con IA

## 📋 Resumen Ejecutivo

KYBER integra **5 funcionalidades de Inbox Zero** que trabajan automáticamente durante cada escaneo de correos. La IA de Gemini analiza cada correo y el sistema registra información en tablas de base de datos para mantener tu bandeja limpia.

---

## 🔍 1. NUEVOS REMITENTES

### ¿Cómo funciona?
Durante cada escaneo, el sistema:

1. **Extrae el email** del remitente de cada correo
2. **Registra en la tabla `remitentes_conocidos`** con:
   - Email del remitente
   - Nombre completo
   - Fecha de primer contacto
   - Contador de correos recibidos
   - Estado (nuevo/aprobado)

3. **Detecta si es primera vez** que te escribe
4. **Muestra en la vista** todos los remitentes nuevos pendientes de revisar

### Tabla en Base de Datos
```sql
CREATE TABLE remitentes_conocidos (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    nombre TEXT,
    primera_vez TIMESTAMP,
    total_correos INTEGER DEFAULT 1,
    aprobado INTEGER DEFAULT 0,
    usuario_id INTEGER
);
```

### Acciones Disponibles
- ✅ **Aprobar**: Marca el remitente como conocido
- 🚫 **Bloquear**: Mueve a lista negra y elimina futuros correos

---

## 🚫 2. BLOQUEADOS Y SILENCIADOS

### ¿Cómo funciona?
Durante cada escaneo, el sistema:

1. **Verifica cada remitente** contra la tabla `remitentes_bloqueados`
2. **Si está bloqueado**: Elimina el correo automáticamente de Gmail
3. **Si está silenciado**: Marca como leído y archiva

### Tabla en Base de Datos
```sql
CREATE TABLE remitentes_bloqueados (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    nombre TEXT,
    tipo TEXT DEFAULT 'bloqueado',  -- 'bloqueado' o 'silenciado'
    razon TEXT,
    fecha_bloqueo TIMESTAMP,
    usuario_id INTEGER
);
```

### Tipos de Bloqueo
- **Bloqueado**: Elimina correos automáticamente
- **Silenciado**: Archiva sin notificar

---

## 📬 3. SUSCRIPCIONES

### ¿Cómo funciona?
Durante cada escaneo, el sistema:

1. **Analiza el email del remitente** buscando patrones:
   - `newsletter@`, `marketing@`, `noreply@`, `no-reply@`, `info@`, `news@`

2. **Busca en el cuerpo** palabras clave:
   - "unsubscribe", "cancelar suscripción", "darse de baja"

3. **Extrae el link de cancelación** usando regex:
   ```python
   r'(https?://[^\s<>"]+(?:unsubscribe|opt-out|remove|cancelar|baja)[^\s<>"]*)'
   ```

4. **Registra en la tabla `suscripciones`** con:
   - Email del remitente
   - Nombre
   - Link de cancelación (si existe)
   - Contador de correos
   - Fecha del último correo
   - Estado (activa/cancelada)

### Tabla en Base de Datos
```sql
CREATE TABLE suscripciones (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    nombre TEXT,
    link_cancelacion TEXT,
    total_correos INTEGER DEFAULT 1,
    ultimo_correo TIMESTAMP,
    estado TEXT DEFAULT 'activa',
    usuario_id INTEGER
);
```

### Acciones Disponibles
- 🔗 **Cancelar**: Abre el link de cancelación en nueva pestaña
- ✓ **Marcar como Hecho**: Marca la suscripción como cancelada

---

## 🧹 4. LIMPIEZA INTELIGENTE

### ¿Cómo funciona?
La IA analiza tu bandeja y sugiere:

1. **Correos antiguos** (>90 días) que pueden eliminarse
2. **Correos leídos antiguos** que ya no necesitas
3. **Correos de categorías específicas** acumulados

### Sugerencias Automáticas
El sistema genera sugerencias basadas en:
- Antigüedad de correos
- Estado de lectura
- Categoría asignada por IA
- Frecuencia de interacción

### Acción
- 🗑️ **Eliminar**: Borra permanentemente los correos sugeridos

---

## ⚙️ 5. ORGANIZACIÓN AUTOMÁTICA

### ¿Cómo funciona?
Creas reglas que se ejecutan automáticamente:

### Tabla en Base de Datos
```sql
CREATE TABLE reglas_organizacion (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT,  -- 'archivar', 'eliminar', 'etiquetar'
    condicion_campo TEXT,  -- 'dias_antiguedad', 'categoria', 'remitente'
    condicion_valor TEXT,
    accion TEXT,
    activa INTEGER DEFAULT 1,
    usuario_id INTEGER
);
```

### Ejemplos de Reglas
1. **Archivar leídos antiguos**
   - Condición: `dias_antiguedad > 30`
   - Acción: Archivar automáticamente

2. **Eliminar anuncios**
   - Condición: `categoria = ANUNCIO`
   - Acción: Eliminar

3. **Organizar por remitente**
   - Condición: `remitente = ejemplo@empresa.com`
   - Acción: Etiquetar como "Importante"

---

## 🤖 Integración con IA de Gemini

### Durante el Escaneo
La IA de Gemini analiza cada correo y:

1. **Clasifica en categorías** (1 palabra, automática)
2. **Detecta intención** (cotización, consulta, soporte, etc.)
3. **Identifica idioma** del correo
4. **Genera respuesta** si es necesario
5. **Decide acción**: BORRADOR, NADA, MARCAR_LEIDO

### Prompt de IA Mejorado
```python
"""
Analiza este correo y clasifica en UNA PALABRA (máx 20 caracteres).
Sé creativo e inventa la categoría más apropiada según el contenido.

Ejemplos de categorías que puedes inventar:
- COTIZACION, FACTURA, PAGO
- SOPORTE, RECLAMO, CONSULTA
- REUNION, EVENTO, INVITACION
- REPORTE, INFORME, ESTADISTICA
- PERSONAL, FAMILIAR, SOCIAL
- etc.

NO estás limitado a estos ejemplos. Inventa la categoría que mejor describa el correo.
"""
```

---

## 📊 Flujo Completo del Escaneo

```
1. Usuario activa escaneo (manual o automático)
   ↓
2. Sistema obtiene correos no leídos de Gmail
   ↓
3. Para cada correo:
   ├─ Registrar remitente en tabla remitentes_conocidos
   ├─ Verificar si está bloqueado → Eliminar
   ├─ Verificar si está silenciado → Archivar
   ├─ Detectar si es suscripción → Registrar en tabla suscripciones
   ├─ Enviar a IA de Gemini para análisis
   ├─ IA clasifica y decide acción
   ├─ Guardar log en tabla logs
   └─ Ejecutar acción (crear borrador, marcar leído, etc.)
   ↓
4. Aplicar reglas de organización automática
   ↓
5. Actualizar estadísticas y contadores
   ↓
6. Mostrar resultados en dashboard
```

---

## 🎯 Beneficios

### Automatización Total
- ✅ Detección automática de remitentes nuevos
- ✅ Bloqueo automático de spam
- ✅ Identificación de suscripciones
- ✅ Sugerencias inteligentes de limpieza
- ✅ Organización basada en reglas

### Inteligencia Artificial
- 🤖 Categorización dinámica (no hardcodeada)
- 🤖 Análisis de intención
- 🤖 Detección de idioma
- 🤖 Generación de respuestas contextuales

### Control Total
- 👤 Apruebas o bloqueas remitentes nuevos
- 👤 Gestionas tu lista negra
- 👤 Cancelas suscripciones fácilmente
- 👤 Creas reglas personalizadas
- 👤 Revisas sugerencias antes de aplicar

---

## 🔧 Configuración Recomendada

### Para Máxima Automatización
1. Activa el agente automático
2. Configura reglas de organización
3. Revisa nuevos remitentes semanalmente
4. Aplica sugerencias de limpieza mensualmente

### Para Control Manual
1. Escanea manualmente cuando quieras
2. Revisa cada decisión de la IA
3. Aprueba remitentes uno por uno
4. Aplica limpieza selectivamente

---

## 📈 Métricas y Estadísticas

El sistema rastrea:
- Total de remitentes conocidos
- Remitentes bloqueados/silenciados
- Suscripciones activas/canceladas
- Correos procesados por categoría
- Borradores creados
- Correos eliminados/archivados

Todo visible en el dashboard principal.
