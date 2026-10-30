# 🌍 PAN-RAP Municipio

<div align="center">

![PAN-RAP Logo](https://img.shields.io/badge/🌍-PAN--RAP%20Municipio-2ea44f?style=for-the-badge&logo=github&logoColor=white)

## **Tecnosfera Al Servicio De La Biosfera**

**Planet Assembly Network** · **Red Asamblearia Planetaria**

Sistema de votación anónima con integridad criptográfica para gobernanza cívica municipal

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-yellow?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![secp256k1](https://img.shields.io/badge/Curva-secp256k1-orange?logo=bitcoin&logoColor=white)](https://en.bitcoin.it/wiki/Secp256k1)
[![Status: Fase 3](https://img.shields.io/badge/Estado-Fase%203%20✅-success)](#-roadmap)

</div>

---

## 📋 ¿Qué es PAN-RAP?

**PAN-RAP** (**P**lanet **A**ssembly **N**etwork / **R**ed **A**samblearia **P**lanetaria) es un ecosistema de gobernanza cívica descentralizada diseñado para municipios de ~25,000 habitantes.

**PAN-RAP Municipio** es la implementación de referencia del módulo de votación anónima, utilizando firmas ciegas Schnorr sobre la curva elíptica secp256k1 para garantizar:

- 🔐 **Anonimato absoluto**: Ni el Emisor ni la Urna pueden vincular identidad con voto
- 🛡️ **Integridad criptográfica**: Cada voto es verificable públicamente sin revelar el votante
- ⚖️ **Un voto por persona elegible**: Protocolo anti-doble-gasto con tokens ciegos únicos
- 🔍 **Transparencia total**: Urna pública y verificador independiente

> **Filosofía**: La tecnología debe servir a la comunidad, no al revés. PAN-RAP es software libre diseñado para empoderar asambleas ciudadanas, no para controlarlas.

---

## ✨ Características Principales

| Característica | Implementación |
|---|---|
| **Motor Criptográfico** | Blind Schnorr sobre secp256k1 (token de 65 bytes) |
| **Backend** | Python 3.12+ con FastAPI y `coincurve` (libsecp256k1) |
| **Frontend** | JavaScript con `@noble/curves` vendorizado (sin CDN) |
| **Elegibilidad** | Modular: `padron`, `presencial`, `aval`, `eid` |
| **Anonimato** | Sin `usuario_id`, sin timestamps, `WITHOUT ROWID` en la urna |
| **Anti-Doble-Gasto** | `PRIMARY KEY (convocatoria_id, r_prima)` |
| **Censo** | Validación HMAC-SHA256 con secreto por convocatoria |
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
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configurar clave del emisor (OBLIGATORIO para producción)
# Opción A: Variable de entorno (recomendada)
export PANRAP_EMISOR_KEY_HEX="$(openssl rand -hex 32)"

# Opción B: Archivo local (solo desarrollo, NUNCA commiteado)
echo "$(openssl rand -hex 32)" > clave_emisor.hex
chmod 600 clave_emisor.hex
```

### Verificar Instalación

```bash
# Ejecutar tests
pytest tests/ -v

# Resultado esperado:
# 64 passed, 9 xfailed (otras fases pendientes)
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

### Flujo de Votación Completo

#### 1. Crear Convocatoria

```bash
curl -X POST http://localhost:8000/convocatorias \
  -H "Content-Type: application/json" \
  -d '{
    "titulo": "Presupuesto Participativo 2027",
    "texto": "Aprobar el plan de obras públicas",
    "modo_elegibilidad": "padron",
    "nivel_garantia": "alta"
  }'

# Respuesta: {"id": "uuid-convocatoria", "estado": "borrador"}
```

#### 2. Cargar Censo

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/censo \
  -H "Content-Type: application/json" \
  -d '{
    "identificadores": ["dni_123", "dni_456", "dni_789"]
  }'

# Respuesta: {"convocatoria_id": "uuid", "cargados": 3}
```

#### 3. Cambiar Estado a Emisión

```sql
-- En SQLite
UPDATE convocatorias SET estado = 'emision' WHERE id = 'uuid-convocatoria';
```

#### 4. Votante Solicita Token

```bash
curl -X POST http://localhost:8000/convocatorias/{conv_id}/emision/inicio \
  -H "Content-Type: application/json" \
  -d '{"credencial": "dni_123"}'

# Respuesta: {"sid": "sesion_id", "R": "02...33"}
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

### Verificar la Urna

```bash
# Script independiente de auditoría
python scripts/verificador_independiente.py

# Salida esperada:
# VERIFICACIÓN EXITOSA: X votos válidos, 0 inválidos
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
| **S7** | Clave fuera de git | `.gitignore` cubre `clave_emisor.hex` |
| **S8** | Cliente vendorizado | `frontend/lib/` con `@noble/curves` (sin CDN) |

### Manejo de Claves

**⚠️ NUNCA commitear claves reales**

| Método | Uso | Seguridad |
|---|---|---|
| `PANRAP_EMISOR_KEY_HEX` | Producción | ✅ Recomendado |
| `clave_emisor.hex` | Desarrollo | ⚠️ Solo local, `chmod 600` |
| Clave efímera | Tests | ❌ No usar en producción |

### Elegibilidad y Privacidad

- **`persona_ref`**: HMAC-SHA256(secreto_convocatoria, convocatoria:identificador)
- **Secreto por convocatoria**: Almacenado en `convocatorias.secreto_hmac`, nunca expuesto
- **Censo**: Validación contra tabla `personas` antes de emitir
- **Anonimato**: `persona_ref` diferente por convocatoria, no enlazable entre ellas

---

## 🗺️ Roadmap

| Fase | Estado | Descripción |
|---|---|---|
| **Fase 1** | ✅ Completada | Investigación de primitivas (RFC 9474, Blind Schnorr) |
| **Fase 2** | ✅ Completada | Tests rojos (AC-S1, AC-S2, AC-S4) |
| **Fase 3** | ✅ Completada | Elegibilidad modular con censo y `persona_ref` real |
| **Fase 4** | ✅ Completada | Urna pública y verificador independiente |
| **Fase 5** | ✅ Completada | Migración completa a Blind Schnorr |
| **Fase 6** | ⏳ Pendiente | **Auditoría criptográfica externa** |
| **Fase 7** | ⏳ Pendiente | Despliegue piloto en municipio real |

> ⚠️ **Estado actual**: Prototipo funcional. **NO apto para uso vinculante** hasta completar Fase 6.

---

## 📚 Documentación

- [01-spec-v0.md](docs/01-spec-v0.md) — Especificación general
- [02-investigacion-rfc9474.md](docs/02-investigacion-rfc9474.md) — Investigación de RSA Blind (alternativa)
- [03-motor-blind-schnorr.md](docs/03-motor-blind-schnorr.md) — Motor actual (Blind Schnorr)
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

*"Tecnosfera Al Servicio De La Biosfera"*

[![GitHub](https://img.shields.io/badge/GitHub-amurlaniakea-181717?logo=github&logoColor=white)](https://github.com/amurlaniakea)
[![License](https://img.shields.io/badge/License-AGPL%20v3-blue?logo=gnu&logoColor=white)](LICENSE)

</div>
