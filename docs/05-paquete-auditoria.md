# 05 — Paquete para la auditoría externa (Fase 6b)

> Estado: **borrador para enviar a revisores**. Describe qué se pide revisar, qué afirma el sistema y cómo reproducirlo. No sustituye al [modelo de confianza](04-modelo-de-confianza.md), que declara lo que el sistema **no** garantiza.

## 1. Qué se pide

Una revisión criptográfica y de seguridad de aplicación del prototipo **PAN-RAP Municipio** (votación anónima con firma ciega Schnorr sobre secp256k1), con informe de hallazgos con severidad, prueba de concepto cuando sea posible y recomendación. Código bajo AGPL-3.0-or-later; los hallazgos se coordinarán de forma privada antes de publicarse.

**Versión a revisar:** el commit que Pedro marque con `git tag auditoria-6b` (congelar antes de enviar; la CI de GitHub debe estar en verde).

## 2. Alcance y prioridad

| Prioridad | Componente | Líneas | Qué contiene |
|---|---|---|---|
| 1 | `emisor_schnorr.py` | 89 | Emisor: una sesión abierta, `k` efímero, `s = k + d·e` con libsecp256k1, TTL de 10 s |
| 1 | `urna_schnorr.py` | 46 | Mensaje, desafío `SHA-256(T‖T‖R'‖Y‖m) mod q` y verificación pública (fail-closed) |
| 1 | `claves.py` | 80 | Clave maestra (fail-closed), derivación HMAC-SHA256 de una clave de firma y una de registro por convocatoria |
| 1 | `main.py` (`inicio`, `fin`, `votar`, `_sellar`, `_exigir_claves`) | ~250 de 721 | Transaccionalidad de la emisión, guarda de claves, validación de votos, sellado de checkpoints |
| 2 | `registro.py` | 173 | Árbol de Merkle RFC 6962, checkpoints firmados y encadenados, verificación, equivocación |
| 2 | `scripts/verificador_independiente.py`, `scripts/observador.py` | 115 + 103 | Verificación pública y archivo de checkpoints |
| 2 | `frontend/src/*.mjs`, `frontend/build.js`, `frontend/ui/*` | ~260 | Cliente del votante (cegado en el navegador), CSP, bundle reproducible |
| 3 | `backend/schema.sql`, autenticación de administración y validación de entradas en `main.py` | 57 | Esquema v3, `X-Admin-Token`, restricciones de estado |

**Fuera de alcance:** modos de elegibilidad `presencial`, `aval` y `eid` (no implementados; los endpoints devuelven 501), despliegue (TLS, proxy, backups, rotación y custodia de la clave maestra), infraestructura de observadores, y los tests heredados marcados `xfail` (`test_voting_rules.py`, `test_capacity_constraints.py`, `test_proposal_workflow.py`).

## 3. Propiedades que el sistema afirma (y dónde se prueban)

| # | Propiedad | Implementación | Pruebas |
|---|---|---|---|
| P1 | Corrección de Blind Schnorr: el token `(R', s')` verifica con `Y` | `emisor_schnorr.py`, `urna_schnorr.py` | `test_emisor_schnorr.py`, `test_urna_schnorr.py`, `test_motor_schnorr.py`, `test_cliente_js.py::test_nucleo_js_coincide_con_python` |
| P2 | Una sola sesión de firma abierta por clave; `k` se destruye siempre | `Emisor.inicio/fin` | `test_emisor_schnorr.py`, `test_emisor_sid_activo.py` |
| P3 | Un token de una convocatoria no vale en otra (clave y mensaje ligados) | `claves.derivar_clave_convocatoria`, `votar` verifica con la `Y` guardada | `test_flujo_api.py::test_token_de_una_convocatoria_no_vale_en_otra` |
| P4 | Una persona del censo obtiene como máximo una firma | `inicio`/`fin` transaccionales, `emisiones` | `test_flujo_api.py::test_no_se_puede_emitir_dos_veces`, `::test_sesion_viva_no_se_pierde_por_otro_votante`, `::test_abandono_permite_reintento_y_bloquea_al_tercero`, `::test_fin_con_e_invalida_400_y_se_puede_reintentar` |
| P5 | Sin doble gasto del token | `PRIMARY KEY (convocatoria_id, r_prima)` | `test_flujo_api.py::test_opcion_ajena_y_opciones_propias`, `test_e2e_api.py` |
| P6 | Los votos solo se aceptan en convocatorias abiertas, con opción válida y firma verificable | `votar` | `test_flujo_api.py` (sección T6) |
| P7 | Los endpoints de administración exigen token; sin token configurado fallan cerrados | `require_admin` | `test_auth_admin.py` |
| P8 | Un reinicio con otra clave maestra no consume emisiones ni firma checkpoints | `_exigir_claves` | `test_guarda_claves.py` |
| P9 | Registro: retirar o alterar un voto sellado, o reescribir la historia, es detectable con observadores | `registro.py`, `_sellar` | `test_registro.py`, `test_registro_api.py` (con mutantes) |
| P10 | El cliente produce tokens que la urna acepta; el bundle publicado se reconstruye idéntico | `frontend/src/voto_core.mjs`, `build.js` | `test_cliente_js.py` (vectores JS↔Python, votación real desde Node, UI con DOM), CI |
| P11 | El censo no guarda identificadores en claro | `Padron.derivar_ref`, `cargar_censo` | `test_flujo_api.py::test_censo_inserta_personas_y_no_guarda_identificadores` |

Las pruebas se comprobaron con **mutantes** (reintroducir a propósito los fallos: auth que siempre pasa, borrar emisiones ajenas, verificar con una clave global, no sellar al cerrar, no recalcular raíces, quitar la guarda de claves) y fallan en todos ellos.

## 4. Adversarios considerados

| | Adversario | Capacidades |
|---|---|---|
| A1 | Votante malicioso | Varias sesiones, token propio, manipula `a`, `b`, `e`, reintenta, usa tokens entre convocatorias |
| A2 | Atacante externo | Solo API pública: enumeración de credenciales, DoS, entradas malformadas |
| A3 | Operador curioso | Lee BD, logs, IP y tiempos; no modifica código |
| A4 | Operador malicioso | Posee la clave maestra: puede firmar, fabricar votos, descartar o reordenar, servir historias distintas |
| A5 | Coacción / compra de votos | El votante conoce `(R', s')` y puede enseñarlo |
| A6 | Servidor del cliente malicioso | Sirve JavaScript modificado en `/ui` |

Se declaran **no cubiertos** (ver modelo de confianza): A3 (correlación), el relleno de urna por A4 con claves válidas, el descarte de votos aún sin sellar, A5 y A6 sin comprobación del hash del bundle.

## 5. Preguntas concretas para los revisores

**Protocolo y claves**
1. ¿Es suficiente la emisión **secuencial** (una sesión abierta por clave, TTL de 10 s, sesión caducada sustituida por otra nueva) frente a los ataques ROS/Wagner sobre Blind Schnorr, o se recomienda otra mitigación (p. ej. variante con *clause blind signatures* u otro esquema)?
2. El desafío es `e' = SHA-256(T‖T‖R'‖Y‖m) mod q` con `T = SHA-256("PANRAP-BSCHNORR-v1")` y `m = "PANRAP-v1|conv|opción"`. ¿Hay problemas de separación de dominios, de reducción módulo `q` (sesgo) o de ambigüedad en `m`?
3. Derivación de claves: `d = HMAC-SHA256(master, "PANRAP-KEY-v1|conv_id|n")` (y `PANRAP-LOG-v1` para el registro), con `n` creciente hasta que libsecp256k1 acepte el escalar. ¿Es adecuada la separación entre clave de firma y de registro? ¿Hay ataques de claves relacionadas entre convocatorias? ¿Qué política de custodia, copia y rotación de la clave maestra recomiendan?
4. El cliente elige `a, b` como 512 bits aleatorios reducidos mod `q`, comprueba `s·G = R + e·Y` y el token final antes de usarlos. ¿Falta alguna comprobación (puntos en el infinito, subgrupo, encodings no canónicos de `R` o `Y`)?

**Emisión y estado**
5. En `fin`, la fila de `emisiones` pasa a `completada` **antes** de liberar `s`, dentro de una transacción `BEGIN IMMEDIATE` con rollback si `Emisor.fin` falla. ¿Existe alguna secuencia (caída entre `COMMIT` y la respuesta, reintentos, concurrencia con varios procesos) en la que se libere más de una `s` por persona, o en la que `s` se libere sin dejar rastro?
6. El mensaje de error de `inicio` es único («Credencial inválida o ya utilizada»). ¿Existen diferencias de **tiempo** o de código de respuesta entre «no está en el censo», «ya emitió» y «bloqueada» que permitan enumerar el censo?
7. La clave del HMAC de `persona_ref` (`secreto_hmac`) está en la misma BD. Con la BD filtrada, ¿es viable recuperar quién está en el censo (espacio de identificadores pequeño, p. ej. DNI)?

**Registro de la urna**
8. Los checkpoints firman con ECDSA (libsecp256k1 vía coincurve) y el hash encadenado incluye los **bytes DER** de la firma. ¿Puede la maleabilidad de ECDSA/DER alterar el encadenamiento sin invalidar la firma? ¿Debería firmarse con Schnorr/BIP-340 o fijarse codificación canónica?
9. El árbol usa el esquema RFC 6962 con hojas `r'‖s'‖len‖opción` y orden `(lote, r')`. ¿Se filtra información útil con `n` por lote y con el orden entre lotes? ¿Qué tamaño de lote recomiendan?
10. ¿Qué garantías adicionales aportaría anclar los checkpoints en un tercero (transparencia tipo CT, sellos de tiempo, o varios observadores con cuórum)?

**Aplicación y cliente**
11. Revisión de la superficie de la API: validación de entradas, inyección SQL (consultas parametrizadas; el único SQL construido por concatenación en `actualizar_convocatoria` usa nombres de columna constantes), control de estados, ausencia de límites de tasa, y un único `X-Admin-Token` compartido.
12. Cliente: política CSP (`default-src 'none'; script-src 'self'; …`), generación de aleatoriedad, dependencias (`@noble/curves` 1.9.7, `@noble/hashes` 2.4.0, `esbuild` 0.28.2, fijadas) y reproducibilidad del bundle. ¿Qué mecanismo recomiendan para que el votante verifique que el JavaScript servido es el publicado?
13. Privacidad: anonimato frente al operador (A3). ¿Qué combinación de retardos aleatorios, mezcla o canal anónimo recomiendan como mínimo para un piloto?

## 6. Cómo reproducir

```bash
git clone https://github.com/amurlaniakea/pan-rap-municipio.git && cd pan-rap-municipio
git checkout auditoria-6b                          # etiqueta que Pedro fijará antes de enviar
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
npm ci                                             # @noble/* y esbuild con versiones exactas
python -m pytest -q                                # todos los tests; los xfailed son heredados
node frontend/build.js && git diff --exit-code -- frontend/ui/voto.bundle.js frontend/SHA256SUMS   # bundle reproducible
(cd frontend && sha256sum -c SHA256SUMS)

# Servidor de pruebas y demo
export PANRAP_ADMIN_TOKEN="$(openssl rand -hex 32)" PANRAP_ALLOW_EPHEMERAL_KEY=1
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
python scripts/demo_local.py                       # crea una convocatoria abierta con 3 votantes
```

Para ejercitar el registro: `python scripts/observador.py <conv_id> --log-pub <hex> --cada 10` durante la votación y `python scripts/verificador_independiente.py <conv_id> --Y <hex> --log-pub <hex> --archivo observador_<conv_id>.jsonl` al cerrar.

## 7. Limitaciones conocidas que no hace falta reportar

Las de [04-modelo-de-confianza.md](04-modelo-de-confianza.md), más: sin límite de tasa; un solo proceso (`--workers 1`; el cerrojo es en memoria); sin registro de auditoría de las acciones de administración; sin TLS en la aplicación (se espera detrás de un proxy); fechas de convocatoria no aplicadas; esquema de BD sin migraciones; clave efímera permitida solo con `PANRAP_ALLOW_EPHEMERAL_KEY=1`.

## 8. Entregable esperado

Informe con: resumen ejecutivo, hallazgos (severidad, componente, descripción, PoC, recomendación), respuestas a las preguntas de la §5 y lista de lo no revisado. Los revisores pueden publicar el informe tras un plazo de divulgación coordinada acordado con Pedro.

## 9. Lista de comprobación antes de enviar (para Pedro)

- [ ] CI de GitHub en verde en el commit a revisar.
- [ ] `git tag auditoria-6b <commit> && git push origin auditoria-6b`.
- [ ] Decidir y documentar la custodia de la clave maestra (dónde vive, quién tiene copia) para el piloto.
- [ ] Contacto de divulgación (correo) y plazo (p. ej. 90 días).
- [ ] Al menos un observador independiente probado de extremo a extremo con `scripts/observador.py`.
