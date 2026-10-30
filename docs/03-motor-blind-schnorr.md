---
title: PAN-RAP Municipio — Motor de voto Blind Schnorr (secp256k1)
created: 2026-10-26
updated: 2026-10-26
type: spec
status: borrador-v0.2
tags: [pan-rap-municipio, sdd, spec, criptografia, schnorr]
sources: ["prototipo sandbox/blind_schnorr (repo)", "Benhamouda et al., On the (in)security of ROS (Eurocrypt 2021)", "pruebas ejecutadas 2026-10-26 (reproducir-schnorr.sh)"]
---

# Motor de voto: Blind Schnorr sobre secp256k1

> **Decisión de Pedro (2026-10-26):** el motor criptográfico es Blind Schnorr sobre ECC (secp256k1), cliente con `@noble/curves`. Este documento la adopta y fija las condiciones para que sea seguro. **Sustituye** de `01-spec-v0.md`: §5.2–5.6 (protocolo), la tabla `emisiones`/`votos` de §7, §8 (claves), los endpoints de emisión y voto de §9, y los criterios AC-06 y AC-17. **Todo lo demás de la Spec sigue vigente** (convocatorias, ventanas, elegibilidad modular, urna pública, acta). RSA/RFC 9474 queda documentado en `02-investigacion-rfc9474.md` como alternativa, no se borra.

## 1. Por qué Schnorr (las razones de Pedro, comprobadas)

| Razón | Comprobación |
|---|---|
| Token pequeño | `(R', s')` = 33 + 32 = **65 bytes**, frente a 384 de RSA-3072 |
| Rapidez | operaciones de curva en milisegundos; el cliente usa `@noble/curves` |
| La opción va dentro de la firma | el voto no se puede cambiar en tránsito (cierra R-14 de la Spec; ya no hace falta OQ-08) |
| Firmas distintas por votante sin nonce propio | el cegado aleatorio `(a, b)` hace único cada `R'` |

Contrapartida honesta: **no hay RFC ni vectores oficiales** para Blind Schnorr; por eso las condiciones de §4 y las pruebas de §8 son obligatorias.

## 2. ¿Estaba resuelto el motor? Lo que había y lo que faltaba

| Pieza | Estado | Evidencia |
|---|---|---|
| Matemática de Blind Schnorr (`sandbox/blind_schnorr/prototipo_schnorr.js`) | **Correcta** para una sesión (usa `e = e' + b`) | ejecutado: firma válida |
| Motor conectado a la API (`main.py`) | **Era RSA "de libro" y no funcionaba** | tu salida `--runxfail`: `TypeError: Hash.finalize() takes no arguments`, `NameError: BytesIO`, `IntegrityError … usuario_id` |
| `verificar_firma_ecc` | Era un *stub* que aceptaba cualquier firma | ahora lanza `NotImplementedError` |
| Esquema de base de datos, sesiones, verificación pública, pruebas | **No existían** | — |

Tu intuición era correcta: el núcleo matemático de Schnorr estaba bien. Lo que faltaba era el protocolo completo alrededor.

## 3. Protocolo

```
Curva secp256k1: orden q, generador G.
Emisor, por convocatoria: d (secreta) e Y = d·G (pública, 33 B comprimida).
T  = SHA-256("PANRAP-BSCHNORR-v1")
H(R', m) = SHA-256( T ‖ T ‖ R'(33 B) ‖ Y(33 B) ‖ m )  mod q          (incluye la clave Y)
m  = "PANRAP-v1|" ‖ convocatoria_id ‖ "|" ‖ opcion

1. EMISOR (sesión autenticada): k ← CSPRNG en [1, q−1];  R = k·G.  Envía R.
2. CLIENTE: a, b ← CSPRNG en [1, q−1];  R' = R + a·G + b·Y   (si R' es el infinito, repetir)
            e' = H(R', m);   e = e' + b  (mod q).   Envía e.
3. EMISOR:  comprueba 0 < e < q;  s = k + d·e  (mod q);  destruye k.  Envía s.
4. CLIENTE: comprueba s·G = R + e·Y (si no, aborta);  s' = s + a  (mod q).
            Token = (R', s'): 65 bytes.
5. VERIFICACIÓN PÚBLICA:  s'·G = R' + H(R', m)·Y.
```

Comprobación algebraica: `s'G = (k + d·e + a)G = R + eY + aG` y `R' + e'Y = R + aG + bY + e'Y = R + aG + eY`. Coinciden **solo** con `e = e' + b`.

El voto se envía a la Urna como `{convocatoria_id, opcion, R', s'}`. La clave anti-doble-gasto es `R'`.
La **opción se decide antes de pedir la firma** (va dentro de `m`). Tras la firma el voto es irrevocable (OQ-01 de la Spec, valor por defecto).

## 4. Condiciones de seguridad (innegociables)

| ID | Condición | Por qué |
|---|---|---|
| S1 | **Emisión secuencial: una sola sesión abierta en todo el Emisor**, con caducidad de 10 s. El Emisor corre en **un proceso** o con un cerrojo compartido y atómico. | Blind Schnorr plano se rompe con sesiones concurrentes (ataque ROS, §6) |
| S2 | Una emisión **completada** por (convocatoria, persona). Hasta 3 sesiones fallidas o caducadas (configurable); después, bloqueo y aviso al registrador. | evita DoS por el cerrojo y múltiples tokens |
| S3 | El cliente comprueba `s·G = R + e·Y` y que `Y` coincide con el SHA-256 publicado en la convocatoria y en el acta. Todos los votantes reciben la **misma** `Y`. | anti-partición del anonimato (R-16 de la Spec) |
| S4 | Todo cálculo con secretos (`k`, `d`, `s = k + d·e`) lo hace **libsecp256k1** (vía `coincurve`). **Prohibidos enteros de Python sobre secretos.** | `cryptography` no sirve aquí (§5) |
| S5 | `k` se genera con CSPRNG en cada sesión, vive en memoria hasta `fin` o caducidad y se destruye. Reutilizar `k` con dos `e` distintos **revela `d`**. | |
| S6 | Validación estricta: `0 < e < q`, longitud exacta de cada campo, `R'` punto válido en la curva, `0 < s' < q`. | fail-closed (K5) |
| S7 | La clave `d` vive en un archivo con permisos `0600` fuera de git (no en una variable de entorno, que aparece en `/proc` y en volcados). Una clave por convocatoria; se destruye tras `escrutada`. | K7 |
| S8 | Cliente `@noble/curves` **vendorizado** con su SHA-256 publicado; sin CDN. `a`, `b` salen de `crypto.getRandomValues`. | el servidor que sirve el JS podría servir uno trucado (R-21) |

## 5. Correcciones al texto de la otra asistente y a la discusión

| Afirmación | Veredicto | Evidencia |
|---|---|---|
| "`e = e_ciego − b`" (spec pegada) | **Falso: el voto sale inválido** | probado: variante `e' + b` VÁLIDA, variante `e' − b` INVÁLIDA; el prototipo del repo ya usaba `+ b` |
| "Con `cryptography` no hace falta aritmética propia" | **Falso** | `cryptography` no ofrece suma de puntos ni aritmética de escalares mod q; la verificación `R' + e'·Y` no se puede calcular con ella. `coincurve` (libsecp256k1) sí: probado |
| "Ceguera condicional: un Emisor malicioso averigua la opción por fuerza bruta" | **No aplica** | la opción es **pública** en el voto; y la ceguera no depende de la entropía del mensaje: para cualquier voto publicado existe un par `(α, β)` compatible con **cada** transcripción del Emisor (probado 144/144) |
| "El nonce de 256 bits cierra el ataque" | **Inocuo pero innecesario** para la ceguera; **no** resuelve el riesgo real (ROS) | las firmas ya son únicas por el cegado `(a, b)` |
| "Tan seguro como RSA Blind" | **No equivalente** | RSABSSA tiene RFC y demostración; Blind Schnorr plano no tiene estándar y exige S1 |
| "ZK-proofs o VOPRF hacen falta" | **No** | sobreingeniería para este modelo (con S1) |
| "`UNIQUE(propuesta, R, s)` previene el doble gasto" | **Insuficiente** | lo que limita los tokens es S2 (una emisión por persona y convocatoria) |
| `solicitudes_firma.usuario_id UNIQUE` | **Repite el fallo C2** | una firma por usuario *de por vida*; debe ser por (convocatoria, persona) |
| `votos.id AUTOINCREMENT` y `timestamp` | **Rompe el anonimato por orden** | usar `WITHOUT ROWID`, sin marcas de tiempo |
| "`@noble/curves` es 100 % tiempo constante" | **Sin verificar** | JavaScript no garantiza tiempo constante; en el cliente solo afecta a un atacante local. **NO VERIFICADO** en su documentación |
| "RSA descartado y borrado" | **No** | queda como alternativa documentada |

**Corrección mía.** En mi primera auditoría escribí que falsificar firmas "equivale a votos ilimitados". Era exagerado: el ataque ROS produce **ℓ + 1 firmas con ℓ sesiones concurrentes**, así que con una sesión por persona la ganancia es **+1 por cada ≥ 256 sesiones concurrentes**. Aun así rompe el invariante K1 (una persona, un voto), y por eso S1 es obligatoria.

## 6. Riesgos del motor (se suman a la tabla de la Spec)

| ID | Riesgo | Mitigación | Residual |
|---|---|---|---|
| R-02′ | Forja de tokens | S1: con sesiones secuenciales la seguridad se apoya en resultados para Blind Schnorr no concurrente (Fuchsbauer–Plouviez–Seurin, Eurocrypt 2020, **NO VERIFICADO aquí**) | no es un estándar; revisión externa (Fase 6) |
| R-16′ | **ROS** si algo reintroduce concurrencia (varios procesos, réplicas, cerrojo roto) | S1, AC-S2 | polinómico para ℓ > log₂ q ≈ 256 sesiones (según el resumen del artículo consultado) |
| R-17 | DoS: alguien mantiene el cerrojo abierto | autenticado, caducidad 10 s, 3 intentos, contadores públicos | un atacante con N cuentas puede ocupar N × 10 s |
| R-18 | Reutilización de `k` (filtra `d`) | S5, AC-S3 | — |
| R-19 | Aritmética con secretos fuera de libsecp256k1 | S4, AC-S8, revisión de código | que `libsecp256k1` sea de tiempo constante lo afirma su documentación; **NO VERIFICADO aquí** |
| R-20 | Protocolo sin estándar ni auditoría | "no apto para uso real" hasta la Fase 6 | total hasta entonces |
| R-21 | El servidor sirve un cliente JS trucado | S8, hash del cliente publicado, copia local verificable | usuario que no verifica |
| R-22 | ECC no es post-cuántica | la urna publicada queda fija; clave destruida tras el cierre | convocatorias abiertas |

**Capacidad.** Con una sola sesión abierta a la vez y ~0,5 s por sesión (dos viajes de red), 26 000 votantes ocupan ~3,6 h de cerrojo. La ventana de emisión (≥ 48 h, §5.1 de la Spec) lo absorbe, siempre que los votantes no se concentren en la última hora.

## 7. Cambios en datos y API

```sql
-- Almacén A (identidad): sustituye a la tabla emisiones de la Spec
CREATE TABLE emisiones (
  convocatoria_id TEXT NOT NULL,
  persona_ref     TEXT NOT NULL,
  estado          TEXT NOT NULL CHECK (estado IN ('pendiente','completada','bloqueada')),
  intentos        INTEGER NOT NULL DEFAULT 0,       -- sesiones fallidas o caducadas
  PRIMARY KEY (convocatoria_id, persona_ref),
  FOREIGN KEY (convocatoria_id, persona_ref) REFERENCES personas(convocatoria_id, persona_ref)
);                                                  -- sin R, e, s ni marcas de tiempo

-- Almacén B (urna): sustituye a la tabla votos de la Spec
CREATE TABLE votos (
  convocatoria_id TEXT NOT NULL REFERENCES convocatorias_pub(id),
  r_prima         BLOB NOT NULL CHECK (length(r_prima) = 33),   -- R' (id anti doble gasto)
  s_prima         BLOB NOT NULL CHECK (length(s_prima) = 32),
  opcion          TEXT NOT NULL,
  PRIMARY KEY (convocatoria_id, r_prima)
) WITHOUT ROWID;
```

`convocatorias.emisor_pub_pem` pasa a `emisor_pub_hex` (33 bytes) más su SHA-256.

| Ruta | Auth | Petición | Respuesta | Errores |
|---|---|---|---|---|
| `POST /convocatorias/{id}/emision/inicio` | credencial | — | `{sesion, R}` | 401, 403, 409 (ya completada), **503** `emision_ocupada` con `Retry-After`, 423 bloqueada |
| `POST /convocatorias/{id}/emision/fin` | credencial | `{sesion, e}` | `{s}` | 400, 401, 409 (sesión inválida o caducada) |
| `POST /convocatorias/{id}/votos` | ninguna | `{opcion, R_prima, s_prima}` | `201 {id: R'}` | 400 inválido, 409 token gastado o convocatoria no abierta |

## 8. Criterios de aceptación del motor

| ID | Criterio |
|---|---|
| AC-S1 | Interoperabilidad: cliente `noble` ↔ Emisor `coincurve` ↔ verificador independiente (implementación de referencia en Python puro, solo en tests) concuerdan en 1 000 firmas; cada campo mutado (`opcion`, `R'`, `s'`, `Y`) hace inválida la firma |
| AC-S2 | Con una sesión abierta, `inicio` → 503; con 50 clientes concurrentes el máximo de sesiones simultáneas observado es **1** |
| AC-S3 | 10 000 sesiones → 10 000 `R` distintos; `k` no queda en disco ni tras `fin` o caducidad |
| AC-S4 | `e` = 0, `e` ≥ q, longitudes erróneas, punto inválido o `s'` fuera de rango → 400, y ninguna entrada inválida completa una emisión |
| AC-S5 | **Ceguera:** toda transcripción del Emisor es compatible con todo voto publicado (N = 100) |
| AC-S6 | El cliente rechaza una `Y` cuyo SHA-256 no coincide con el publicado; todos los clientes reciben la misma `Y` |
| AC-S7 | Una emisión completada por (convocatoria, persona); un segundo `fin` → 409; tras el máximo de intentos → bloqueo |
| AC-S8 | Revisión: el módulo del Emisor no usa enteros de Python con `d` o `k`; solo libsecp256k1 |
| AC-S9 | Un voto con una opción distinta de la firmada → rechazado |

Quedan vigentes los AC-01…AC-18 de la Spec salvo: AC-06 (ahora "N `R'` distintos"), AC-17 (sustituido por AC-S1) y AC-14 (equivale a AC-S4).

## 9. Evidencia ejecutada (2026-10-26)

Entorno de pruebas: Python 3.12, `coincurve` 21.0.0, Node 22, `@noble/curves` 1.9.7. Script: **`reproducir-schnorr.sh`** (autocontenido, trabaja en un directorio temporal).

| Prueba | Resultado |
|---|---|
| Ecuación del prototipo (`e = e' + b`) | VÁLIDA |
| Ecuación del texto pegado (`e = e' − b`) | **INVÁLIDA** |
| Segunda sesión con otra abierta | rechazada (503) |
| Cliente JS ↔ Emisor Python, 12 tokens en secuencia | 12/12 válidos, 12/12 `R'` únicos |
| Mutaciones: opción alterada, `s'` alterado, clave de otro emisor | rechazadas |
| Ceguera: transcripción del Emisor frente a cada voto publicado | **144/144 compatibles** |

**NO VERIFICADO / limitaciones:**
- No ejecuté el ataque ROS ni comprobé el resultado de Fuchsbauer–Plouviez–Seurin; lo primero me consta por el resumen del artículo que consulté, lo segundo no.
- No he comprobado que las operaciones de `libsecp256k1` usadas (`tweak_mul`, `tweak_add`) sean de tiempo constante; lo afirma su documentación.
- Probé 12 firmas, no las 1 000 de AC-S1; no hay tests de concurrencia reales (solo el rechazo de una segunda sesión).
- Nada de esto sustituye a la auditoría criptográfica externa (Fase 6).

## 10. Siguiente paso

1. Pedro revisa estas condiciones. Si las acepta, se cierra la decisión.
2. **Fase 2 (tests rojos, sin tocar `main.py`):** convertir §8 en tests, en prompts cortos para Hermes. Primero AC-S1, AC-S2 y AC-S4.
3. Después: esquema (§7), Emisor, Urna, cliente vendorizado y verificador independiente, cada tarea en su propio prompt.

## Historial

- 2026-10-26: v0.2, Claude. Adopta Blind Schnorr por decisión de Pedro; documenta las correcciones al texto de la otra asistente y la rectificación de mi afirmación sobre ROS.
