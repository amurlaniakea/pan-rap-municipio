# 🌍 PAN-RAP Municipio

<div align="center">

![PAN-RAP Logo](https://img.shields.io/badge/🌍-PAN--RAP%20Municipio-2ea44f?style=for-the-badge&logo=github&logoColor=white)

## **Tecnósfera Al Servicio De La Biósfera**

**Planet Assembly Network** · **Red Asamblearia Planetaria**

Sistema de votación anónima con integridad criptográfica para gobernanza cívica municipal

> ⚠️ **Estado real: prototipo.** La firma ciega (Blind Schnorr) está implementada y probada; el flujo servidor de extremo a extremo se está estabilizando (Fase 6a, ver [auditoría](#-estado-y-limitaciones-conocidas)). **No usar en elecciones reales.** El **cliente web de `frontend/` todavía no es compatible** con este servidor.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-yellow?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![secp256k1](https://img.shields.io/badge/Curva-secp256k1-orange?logo=bitcoin&logoColor=white)](https://en.bitcoin.it/wiki/Secp256k1)
[![Status: Prototipo](https://img.shields.io/badge/Estado-Prototipo%20(Fase%206a)-orange)](#-roadmap)

</div>

---

## 📋 ¿Qué es PAN-RAP?

**PAN-RAP** (**P**lanet **A**ssembly **N**etwork / **R**ed **A**samblearia **P**lanetaria) es un ecosistema de gobernanza cívica descentralizada diseñado para municipios de ~25,000 habitantes.

**PAN-RAP Municipio** es la implementación de referencia del módulo de votación anónima, utilizando firmas ciegas Schnorr sobre la curva elíptica secp256k1 para garantizar:

- 🔐 **Anonimato de la firma**: el emisor no ve el mensaje firmado ni el token final. Pero emisor y urna comparten proceso y operador: quien opere el servidor puede correlacionar identidad y voto por IP, tiempos o logs ([modelo de confianza](docs/04-modelo-de-confianza.md))
- 🛡️ **Integridad criptográfica**: Cada voto es verificable públicamente sin revelar el votante
- ⚖️ **Un voto por persona elegible**: Protocolo anti-doble-gasto con tokens ciegos únicos
- 🔍 **Urna pública al cierre**: cada voto se verifica con la clave pública de la convocatoria; el verificador no necesita claves privadas

> **Filosofía**: La tecnología debe servir a la comunidad, no al revés. PAN-RAP es software libre diseñado para empoderar asambleas ciudadanas, no para controlarlas.

---

## ✨ Características Principales

| Característica | Implementación |
|---|---|
| **Motor Criptográfico** | Blind Schnorr sobre secp256k1 (token de 65 bytes) |
| **Backend** | Python 3.12+ con FastAPI y `coincurve` (libsecp256k1) |
| **Frontend** | `frontend/`: cliente en JavaScript **no funcional con este backend** (pendiente de rehacer; ver limitaciones) |
| **Ciclo de Vida** | Transiciones de estado validadas (`borrador` → `programada` → `emision` → `votacion` → `cerrada` → `escrutada` → `archivada`) |
| **Acta PDF** | Generación automática con reportlab al finalizar el escrutinio |
| **Modos de Elegibilidad** | Solo `padron` (censo HMAC). `presencial`, `aval` y `eid` **no están implementados** (los endpoints devuelven 501) |
| **Claves** | Una clave de firma por convocatoria, derivada de la clave maestra del emisor: una firma no vale en otra convocatoria |
| **Administración** | Endpoints de gestión protegidos con `X-Admin-Token` (`PANRAP_ADMIN_TOKEN`, ≥ 32 caracteres) |
| **Urna** | Sin `usuario_id`, sin timestamps, `WITHOUT ROWID`; se publica ordenada por `r_prima` |
| **Anti-Doble-Gasto** | `PRIMARY KEY (convocatoria_id, r_prima)` |
| **Censo** | Solo se guarda `persona_ref` = HMAC-SHA256(secreto de la convocatoria, identificador); los identificadores no se almacenan |
| **Verificación** | Script independiente que audita la urna completa |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR DEL VOTANTE                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  voto_schnorr.js (@noble/curves)                        │   │
│  │  • Genera a, b ← crypto.getRandomValues()              │   │
│  │  • Calcula R' = R + a·G + b·Y                          │   │
│  │  • Calcula e = H(R', m) + b                            │   │
│  │  • Recibe s, calcula s' = s + a                        │   │
│  │  ⚠️ a y b NUNCA salen del navegador                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │ e (público)  │              │ {opcion, R', s'}
              ▼              │              ▼
    ┌─────────────────┐      │    ┌─────────────────┐
    │     EMISOR      │      │    │      URNA       │
    │   (main.py)     │      │    │   (main.py)     │
    │                 │      │    │                 │
    │ • Genera k      │      │    │ • Verifica      │
    │ • Devuelve R    │      │    │   s'·G == R'+e·Y│
    │ • Firma: s=k+d·e│      │    │ • Inserta voto  │
    │                 │      │    │                 │
    │ Ve: e           │      │    │ Ve: R', s'      │
    │ NO ve: a, b, m  │      │    │ NO ve: identidad│
    └─────────────────┘      │    └─────────────────┘
                             │
                    ┌────────┴────────┐
                    │   BASE DE DATOS │
                    │   (SQLite)      │
                    │                 │
                    │ • convocatorias │
                    │ • personas      │
                    │ • emisiones     │
                    │ • votos         │
                    │   (WITHOUT ROWID)│
                    └─────────────────┘
```

---

## 🚀 Instalación

### Requisitos Previos

- Python 3.12 o 3.13 (coincurve aún no soporta 3.14)
- Git
- OpenSSL (para generar claves)

### Instalación Paso a Paso

```bash
# 1. Clonar el repositorio
git clone https://github.com/amurlaniakea/pan-rap-municipio.git
cd pan-rap-municipio

# 2. Crear entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt  # Incluye reportlab para actas PDF
pip install -r requirements-dev.txt

# 4. Configurar clave del emisor y token de administración (el servidor NO arranca sin clave)
export PANRAP_ADMIN_TOKEN="$(openssl rand -hex 32)"
# Solo para pruebas locales sin clave: export PANRAP_ALLOW_EPHEMERAL_KEY=1
# Opción A: Variable de entorno (recomendada)
export PANRAP_EMISOR_KEY_HEX="$(openssl rand -hex 32)"

# Opción B: Archivo local (solo desarrollo, NUNCA commiteado)
echo "$(openssl rand -hex 32)" > clave_emisor.hex
chmod 600 clave_emisor.hex
```

### Verificar Instalación

```bash
# Ejecutar tests
python -m pytest -q

# Resultado esperado: todos pasan (los xfailed son tests heredados marcados como pendientes)
```

---

## 📖 Uso

### Iniciar el Servidor

```bash
# Modo desarrollo (recarga automática)
fastapi dev main.py

# Modo producción
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **Importante**: Usar `--workers 1` en producción. El cerrojo de sesión (S1) requiere un único proceso.

> ⚠️ **Nota de escalabilidad**: El emisor utiliza `threading.Lock()` para garantizar la emisión secuencial. Esto limita el despliegue a un único proceso (`--workers 1`). Para escalar horizontalmente (>1000 votantes/hora), migre el estado de sesión (`sid`, `k`, `ttl`) a Redis con bloqueos distribuidos (`SETNX`) y TTL nativo, permitiendo múltiples workers de Uvicorn. Ver TODO en `emisor_schnorr.py`.

### Flujo de Votación Completo

#### 1. Crear Convocatoria

```bash
curl -X POST http://localhost:8000/convocatorias \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "titulo": "Presupuesto Participativo 2027",
    "texto": "Aprobar el plan de obras públicas",
    "opciones": ["a_favor", "en_contra", "abstencion"],
    "modo_elegibilidad": "padron",
    "nivel_garantia": "alta",
    "emision_abre_en": "2026-11-01T00:00:00",
    "voto_abre_en": "2026-11-02T00:00:00",
    "cierra_en": "2026-11-03T00:00:00"
  }'

# Respuesta: {"id": "uuid-convocatoria", "estado": "borrador"}
```

#### 2. Cargar Censo

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/censo \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "identificadores": ["dni_123", "dni_456", "dni_789"]
  }'

# Respuesta: {"convocatoria_id": "uuid", "recibidos": 3, "cargados": 3}
# El censo solo se puede cargar en estado borrador o programada.
```

#### 3. Cambiar Estado a Emisión

```bash
# Vía API administrativa
curl -X PATCH http://localhost:8000/convocatorias/{conv_id}/estado \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado": "programada"}'

curl -X PATCH http://localhost:8000/convocatorias/{conv_id}/estado \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado": "emision"}'
```

#### 4. Votante Solicita Token

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/emision/inicio \
  -H "Content-Type: application/json" \
  -d '{"credencial": "dni_123"}'

# Respuesta: {"sid": "sesion_id", "R": "02...33"}
# La clave pública de la convocatoria (Y) se obtiene con GET /convocatorias/{conv_id}.
# El cliente cega R con a y b aleatorios y calcula e (ver tests/helpers_api.py: blindar()).
```

#### 5. Votante Envía Desafío Cegado

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/emision/fin \
  -H "Content-Type: application/json" \
  -d '{"sesion": "sesion_id", "e": "03...32"}'

# Respuesta: {"s": "04...32"}
```

#### 6. Votante Envía Voto Anónimo

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/votos \
  -H "Content-Type: application/json" \
  -d '{
    "opcion": "a_favor",
    "r_prima": "02...33",
    "s_prima": "04...32"
  }'

# Respuesta: {"id": "02...33"}
```

#### 7. Transicionar Estado (Administrador)

```bash
# Borrador → Programada
curl -X PATCH http://localhost:8000/convocatorias/{conv_id}/estado \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado": "programada"}'

# Programada → Emisión (abre votación)
curl -X PATCH http://localhost:8000/convocatorias/{conv_id}/estado \
  -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado": "emision"}'
```

#### 8. Consultar Escrutinio (Público)

```bash
curl http://localhost:8000/convocatorias/{conv_id}/escrutinio
# Respuesta: recuento por opción, participación, hash de urna
```

#### 9. Descargar Urna Completa (Público)

```bash
curl http://localhost:8000/convocatorias/{conv_id}/urna
# Respuesta: todos los votos ordenados por r_prima (no por orden de llegada)
```

#### 10. Generar Acta PDF (Solo en estado escrutada)

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/acta -H "X-Admin-Token: $PANRAP_ADMIN_TOKEN" --output acta.pdf
```

### Modos de Elegibilidad

Solo está implementado el modo **`padron`** (flujo anterior). `presencial`, `aval` y `eid` **no están conectados a la emisión**: crear una convocatoria con otro modo devuelve 400 y sus endpoints devuelven 501. Los módulos de `elegibilidad/` se conservan como código de referencia.

### Verificar la Urna

```bash
# Script independiente (solo biblioteca estándar + la verificación Schnorr): no usa la BD ni claves privadas.
# Lo ideal es pasar la clave pública Y obtenida por otro canal (acta, registro público) con --Y.
python scripts/verificador_independiente.py <conv_id> --api http://localhost:8000 --Y <66 caracteres hex>

# Salida correcta (código 0):  VERIFICACIÓN: N válidos, 0 inválidos, 0 duplicados
# Código 10 si hay firmas inválidas, duplicados, recuento o hash incoherentes.
```

---

## 🔒 Seguridad

### Condiciones Innegociables

| ID | Condición | Implementación |
|---|---|---|
| **S1** | Emisión secuencial | `threading.Lock()` + TTL 10s |
| **S4** | Cero aritmética int sobre secretos | Solo `coincurve` (libsecp256k1) |
| **S5** | `k` efímero por sesión | `PrivateKey()` nuevo en cada `inicio()` |
| **S6** | Validación fail-closed | `urna_schnorr.verificar()` captura excepciones |
| **S7** | Clave fuera de git | `.gitignore` cubre `clave_emisor.hex`; el servidor no arranca sin clave (salvo `PANRAP_ALLOW_EPHEMERAL_KEY=1`) y rechaza claves de ejemplo y ficheros con permisos abiertos |
| **S8** | Cliente vendorizado | **No cumplido todavía**: `frontend/lib/` no existe y el cliente no es compatible con el servidor (pendiente) |

### Manejo de Claves

**⚠️ NUNCA commitear claves reales**

| Método | Uso | Seguridad |
|---|---|---|
| `PANRAP_EMISOR_KEY_HEX` | Producción | ✅ Recomendado |
| `clave_emisor.hex` | Desarrollo | ⚠️ Solo local, `chmod 600` (el servidor rechaza permisos más abiertos) |
| Clave efímera | Tests | ❌ No usar en producción |

### Elegibilidad y Privacidad

- **`persona_ref`**: HMAC-SHA256(secreto_convocatoria, convocatoria:identificador)
- **Secreto por convocatoria**: Almacenado en `convocatorias.secreto_hmac`, nunca expuesto
- **Censo**: Validación contra tabla `personas` antes de emitir
- **Anonimato**: `persona_ref` diferente por convocatoria, no enlazable entre ellas

### Privacidad por Defecto (Mitigación de Enumeración)

Los endpoints de emisión (`/emision/inicio`) devuelven un mensaje de error genérico (`400 - Credencial inválida o ya utilizada`) tanto para credenciales inexistentes como para credenciales que ya emitieron. Esto impide a un atacante enumerar qué identidades existen en el censo o determinar quiénes ya votaron.

---

## 🗺️ Roadmap

| Fase | Estado | Descripción |
|---|---|---|
| **Fase 1** | ✅ Completada | Investigación de primitivas (RFC 9474, Blind Schnorr) |
| **Fase 2** | ✅ Completada | Tests rojos (AC-S1, AC-S2, AC-S4) |
| **Fase 3** | ✅ Completada | Elegibilidad modular con censo y `persona_ref` real |
| **Fase 4** | ✅ Completada | Urna pública y verificador independiente |
| **Fase 5** | ✅ Completada | Migración completa a Blind Schnorr |
| **Fase 5.5** | ⚠️ Con defectos | Ciclo de vida, escrutinio y acta PDF; la auditoría del 2026-10-31 halló defectos de integridad en el flujo (ver abajo) |
| **Fase 6a** | 🔧 En curso | Integridad del flujo servidor: autenticación admin, padrón, clave por convocatoria, emisión y votos robustos, verificador. Pendiente: cliente web |
| **Fase 6b** | ⏳ Pendiente | **Auditoría criptográfica externa** |
| **Fase 7** | ⏳ Pendiente | Despliegue piloto en municipio real |

> ⚠️ **Estado actual**: prototipo. **NO apto para uso vinculante** hasta completar Fase 6a y Fase 6b.

---

## 🧭 Estado y limitaciones conocidas

Una auditoría independiente (2026-10-31, ejecutando el código) encontró que el núcleo criptográfico es correcto pero el flujo que lo rodea tenía defectos. Estado:

| Hallazgo | Estado |
|---|---|
| Carga de censo no insertaba personas; la credencial no coincidía con el censo | ✅ corregido (Fase 6a) |
| Endpoints de administración sin autenticación | ✅ corregido |
| `/votos` aceptaba convocatorias inexistentes o cerradas | ✅ corregido |
| Clave global: un token de una convocatoria valía en otra | ✅ corregido (clave por convocatoria) |
| Emisión: sesión abandonada bloqueaba al votante; `fin` marcaba a todos | ✅ corregido (reintento limitado, transacción) |
| Verificador dependía de una clave privada | ✅ corregido |
| DNI en claro en la tabla `personas` | ✅ corregido |
| Cliente web (`frontend/`) incompatible con el servidor (hash del desafío, convocatoria fija, endpoint) | ❌ pendiente |
| Modos `presencial`, `aval`, `eid` | ❌ no implementados |
| Las fechas de la convocatoria no se aplican (el estado se cambia a mano) | ℹ️ por diseño de este prototipo |
| Anonimato frente al operador, emisor que puede fabricar votos, urna sin compromiso verificable durante la votación | ℹ️ ver [modelo de confianza](docs/04-modelo-de-confianza.md) |

---

## 📚 Documentación

- [01-spec-v0.md](docs/01-spec-v0.md) — Especificación general
- [02-investigacion-rfc9474.md](docs/02-investigacion-rfc9474.md) — Investigación de RSA Blind (alternativa)
- [03-motor-blind-schnorr.md](docs/03-motor-blind-schnorr.md) — Motor actual (Blind Schnorr)
- [04-modelo-de-confianza.md](docs/04-modelo-de-confianza.md) — Qué garantiza y qué no garantiza el sistema
- [RFC 9474](https://www.rfc-editor.org/rfc/rfc9474) — RSABSSA (referencia)

---

## 📄 Licencia

Este proyecto está licenciado bajo **AGPL-3.0-or-later**.

```
PAN-RAP Municipio - Sistema de votación anónima con integridad criptográfica
Copyright (C) 2026 Pedro Sordo Martínez

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

---

<div align="center">

**Autor**: Pedro Sordo Martínez  
**Email**: [amurlaniakea@gmail.com](mailto:amurlaniakea@gmail.com)  
**Año**: 2026

*"Tecnósfera Al Servicio De La Biósfera"*

[![GitHub](https://img.shields.io/badge/GitHub-amurlaniakea-181717?logo=github&logoColor=white)](https://github.com/amurlaniakea)
[![License](https://img.shields.io/badge/License-AGPL%20v3-blue?logo=gnu&logoColor=white)](LICENSE)

</div>
