---
title: PAN-RAP Municipio — Constitución
created: 2026-10-26
updated: 2026-10-26
type: constitucion
status: borrador-v0
tags: [pan-rap-municipio, sdd, constitucion]
sources: []
---

# Constitución de PAN-RAP Municipio (v0)

Principios no negociables. Una spec, un plan o una tarea que los contradiga está mal; la constitución no. Cambiarla exige decisión explícita de Pedro y queda fechada al final de este documento.

**Metodología:** Constitución → Spec → Plan → Tasks → Implement → Verify.
**Gobernanza:** Hermes implementa, Claude audita de forma independiente, Pedro autoriza cada merge y push. Specs y borradores viven en esta bóveda, nunca en el repo.

## 1. Invariantes del sistema de voto

| ID | Invariante | Se comprueba con |
|---|---|---|
| K1 | **Una persona, un voto por convocatoria.** | AC-01, AC-03, AC-06 |
| K2 | **Secreto del voto.** Ningún dato persistido (criptográfico o de metadatos) vincula a una persona con su voto, ni siquiera para quien opera el sistema. | AC-07, AC-08 |
| K3 | **Verificabilidad universal.** Con solo datos públicos, cualquiera comprueba que cada voto contado lleva un token válido, que no hay tokens repetidos y que el recuento es correcto. | AC-09, AC-10 |
| K4 | **Transparencia de garantía.** Cada convocatoria publica su modo de elegibilidad, su nivel de garantía y los contadores (votos ≤ emisiones ≤ registrados ≤ censo declarado). Nunca se infla el nivel de garantía. | AC-11, AC-18 |
| K5 | **Fail-closed.** Ante duda, error o dato ausente se rechaza. Ninguna ruta acepta por defecto y los errores no revelan detalles internos. | AC-02, AC-05, AC-14 |
| K6 | **Criptografía sin inventar.** Solo protocolos con descripción pública y revisada, implementados con bibliotecas mantenidas. Todo cálculo con secretos en bibliotecas de tiempo constante (nunca enteros de Python sobre secretos). Validación por interoperabilidad entre implementaciones independientes y, cuando existan, con los vectores oficiales. Prohibido: inventar primitivas o protocolos, RSA "de libro" sin relleno y firmas ciegas Schnorr con sesiones concurrentes (ataque ROS): la emisión es **secuencial**. | AC-S1…AC-S8 |
| K7 | **Secretos fuera de git.** Claves, tokens y datos reales no entran nunca en el repositorio. Una clave de emisor por convocatoria. | AC-13 |
| K8 | **Honestidad de estado.** README, avisos y mensajes describen lo que el sistema hace hoy. Mientras no exista auditoría criptográfica externa (Fase 6), el aviso "No apto para uso real" permanece. | revisión en cada fase |
| K9 | **Datos mínimos.** Se recoge solo lo necesario. La urna no contiene IP ni marcas de tiempo; identidades y urna viven en almacenes separados sin referencias cruzadas. | AC-07 |
| K10 | **Un modo de elegibilidad por convocatoria**, declarado públicamente. Cambiar de modo implica una convocatoria nueva. | AC-12 |

## 2. Invariantes de proceso

| ID | Regla |
|---|---|
| P1 | **Evidencia antes que afirmación.** Ninguna tarea se da por hecha sin la salida cruda de comandos ejecutados. Nadie escribe resultados a mano. |
| P2 | **Un commit por tarea**, con mensajes que describan lo que el commit hace de verdad. |
| P3 | **Sin push ni merge** sin autorización explícita de Pedro. El repo es privado hasta nueva decisión. |
| P4 | **Tests rojos primero (TDD).** Un test que pasa con el bug presente está mal; se reescribe. Prohibido aflojar o quitar `strict`/`xfail` para esquivar un XPASS. |
| P5 | **Copyright y licencia:** `SPDX-License-Identifier: AGPL-3.0-or-later` y `Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>` en las primeras líneas de todo archivo de código. |
| P6 | **Ningún contenido editorial** (specs, notas, borradores, posts) se commitea al repo de código. |
| P7 | **Sin secretos en salidas.** Nunca se imprimen variables de entorno ni claves; para comprobar una variable se usa `echo ${VAR:+set}`. |

## 3. Qué NO promete este sistema (límites reconocidos)

- Resistencia a **coerción y compra de votos**: el votante puede demostrar su voto (ver R-09 de la Spec). Aceptado solo mientras el uso sea no vinculante.
- Seguridad frente a **malware en el dispositivo** del votante.
- **Identidad legal**: el sistema no sustituye a ningún censo oficial; el modo de elegibilidad dice qué se verificó y con qué garantía.
- **Validez jurídica** de los resultados (D3: prototipo no vinculante).

## Historial

- 2026-10-26 (rev. 2): por decisión de Pedro el motor de voto es Blind Schnorr sobre secp256k1 (ver `03-motor-blind-schnorr.md`); K6 se reformula para exigir emisión secuencial y aritmética de secretos solo en bibliotecas de tiempo constante.
- 2026-10-26: v0, redactada por Claude a partir de la auditoría de `pan-rap-municipio` y de las decisiones D1 (voto anónimo con token ciego), D2 (elegibilidad por módulos), D3 (prototipo no vinculante) y D4 (votación por convocatoria). Pendiente de revisión de Pedro.
