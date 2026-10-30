---
title: PAN-RAP Municipio — Spec v0 (voto por convocatoria con token ciego)
created: 2026-10-26
updated: 2026-10-26
type: spec
status: borrador-v0
tags: [pan-rap-municipio, sdd, spec, criptografia, voto]
sources: ["RFC 9474 (RSA Blind Signatures, oct. 2023)", "auditoría Claude de pan-rap-municipio (hallazgos C1–C8, A1–A6)"]
---

# Spec v0 — Voto por convocatoria con token ciego

> Estado: **borrador redactado por Claude, pendiente de revisión de Pedro.** Sin auditoría criptográfica externa. **Motor de voto: Blind Schnorr sobre secp256k1 (decisión de Pedro, 2026-10-26).** Las secciones 5.2–5.6, la tabla `emisiones`/`votos` de §7, §8, los endpoints de emisión y voto de §9 y los criterios AC-06 y AC-17 quedan **sustituidos** por `03-motor-blind-schnorr.md`; el resto sigue vigente. El texto RSA/RFC 9474 de este documento se conserva como alternativa (investigación en `02-investigacion-rfc9474.md`). Subordinada a `00-constitucion.md`.

## 1. Alcance

**Decisiones de partida**

| ID | Decisión | Valor |
|---|---|---|
| D1 | Arquitectura de voto | Anónimo, con firma ciega Schnorr sobre secp256k1 (decisión de Pedro; ver `03`). Alternativa documentada: RSABSSA (RFC 9474) |
| D2 | Elegibilidad | Módulo configurable por municipio (§6); un modo por convocatoria |
| D3 | Alcance | Prototipo **no vinculante** (hipótesis; pendiente de confirmación explícita) |
| D4 | Unidad de votación | Convocatoria, con ventanas y clave propias |

**Dentro del alcance:** ciclo de la convocatoria, emisión de tokens, urna pública, escrutinio verificable, módulos de elegibilidad, acta.
**Fuera del alcance (v0):** debate y aval cruzado por código postal (fase de propuesta, ya existente), canales sin smartphone, uso jurídicamente vinculante, re-votación.

## 2. Glosario

- **Convocatoria:** votación concreta sobre una propuesta, con parámetros públicos y clave propia.
- **Persona / `persona_ref`:** identificador seudónimo opaco de una persona elegible *dentro de una convocatoria* (§6).
- **Credencial de elegibilidad:** lo que permite autenticarse ante el Emisor; depende del modo.
- **Emisor:** servicio que comprueba elegibilidad y firma a ciegas. Ve identidades, no tokens.
- **Urna:** servicio que recibe votos y verifica tokens. Ve tokens, no identidades.
- **Token:** par (mensaje, firma RSA-PSS) válido bajo la clave pública de la convocatoria. Autoriza **un** voto.
- **`token_id`:** SHA-256 del mensaje firmado. Es la clave anti-doble-gasto.

## 3. Actores y confianza

| Actor | Confianza que se le exige | Qué NO debe poder hacer |
|---|---|---|
| Votante | ninguna | votar dos veces, forjar tokens |
| Registrador / ayuntamiento | alta: decide quién es elegible | ver votos |
| Emisor | media: aplica la elegibilidad y firma | ver el contenido de los tokens |
| Urna | media: aplica reglas de gasto y publica | conocer identidades |
| Observador público | ninguna | — (solo verifica) |

El Emisor y la Urna son **lógicamente separados** (almacenes y rutas distintos). Mientras los opere la misma entidad, la separación es técnica, no de confianza (R-05).

## 4. Modelo de amenazas

| ID   | Amenaza (actor)                                                                           | Mitigación en el diseño                                                                                                                     | Riesgo residual                                                                                                                                                     |
| ---- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-01 | Doble voto / reutilizar un token (votante)                                                | `PRIMARY KEY (convocatoria_id, token_id)`; inserción atómica                                                                                | ninguno conocido                                                                                                                                                    |
| R-02 | Forjar un token (votante)                                                                 | verificación RSA-PSS con la clave de la convocatoria                                                                                        | RSA y la biblioteca (K6)                                                                                                                                            |
| R-03 | Obtener varios tokens (votante)                                                           | `PRIMARY KEY (convocatoria_id, persona_ref)` en emisiones; un modo por convocatoria                                                         | Sybil (R-06)                                                                                                                                                        |
| R-04 | Emisor deshonesto o comprometido emite tokens a no elegibles (relleno de urna)            | contadores públicos (votos ≤ emisiones ≤ registrados ≤ censo); registro de altas auditable                                                  | un emisor que falsifique personas *dentro* del censo no se detecta criptográficamente: es riesgo de confianza, y K4 lo hace visible                                 |
| R-05 | Emisor y Urna colusionados, o mismo operador (desanonimización)                           | ceguera del protocolo; sin IP ni marcas de tiempo en la urna; `WITHOUT ROWID`; ventana de emisión previa a la de voto; jitter en el cliente | correlación por metadatos fuera de la aplicación (proxy, logs del sistema). Mitigación operativa: operadores separados, sin logs de acceso, red anónima recomendada |
| R-06 | Sybil: una persona, varias identidades                                                    | depende del modo (§6); el nivel de garantía se publica                                                                                      | aceptado y declarado                                                                                                                                                |
| R-07 | Registrador deshonesto (modo presencial)                                                  | registro de actuaciones por registrador, contadores públicos por registrador, tope diario, doble registrador opcional                       | colusión de registradores                                                                                                                                           |
| R-08 | Observador de red                                                                         | TLS obligatorio; sin cookies ni cabeceras de identidad en el voto                                                                           | la IP es visible para el proveedor de red                                                                                                                           |
| R-09 | Compra o coerción de voto: el votante puede probar su voto (`token_id` público)           | **riesgo aceptado** en uso no vinculante (D3)                                                                                               | bloquea el uso vinculante hasta resolver OQ-02                                                                                                                      |
| R-10 | Compromiso de la clave privada del Emisor                                                 | clave por convocatoria; custodia fuera de la base y de git; destrucción tras el cierre; detección por contadores                            | ventana hasta detectarlo                                                                                                                                            |
| R-11 | DoS en emisión o voto                                                                     | límites de tasa en memoria (sin persistir IP), límites de tamaño de cuerpo, verificación barata                                             | pruebas de carga en Fase 5                                                                                                                                          |
| R-12 | Fuga de orden por almacenamiento (WAL, journal, copias)                                   | `WITHOUT ROWID`; publicación ordenada por `token_id`; compactar y cifrar copias al cierre                                                   | acceso físico a disco en caliente                                                                                                                                   |
| R-13 | Errores de implementación criptográfica (relleno, parsing, tiempos)                       | biblioteca estándar, vectores de prueba en CI, auditoría externa (Fase 6)                                                                   | hasta la Fase 6 el sistema es **no apto para uso real**                                                                                                             |
| R-14 | Carrera de gasto: alguien que observa un token en tránsito lo gasta antes con otra opción | TLS                                                                                                                                         | ver OQ-08 (atar la opción al token con una clave efímera)                                                                                                           |
| R-15 | Malware en el dispositivo del votante                                                     | fuera de alcance                                                                                                                            | total                                                                                                                                                               |

## 5. Protocolo de la convocatoria

### 5.1 Ciclo de vida

```
borrador → programada → emision → votacion → cerrada → escrutada → archivada
```

| Transición | Quién | Efecto |
|---|---|---|
| borrador → programada | administrador | se fijan opciones, ventanas, modo y texto (se publica su SHA-256); el Emisor genera la clave RSA de la convocatoria; se publica su clave pública |
| programada → emision | automática (`emision_abre_en`) | se pueden pedir tokens; todavía no se vota |
| emision → votacion | automática (`voto_abre_en`) | se pueden pedir tokens y votar |
| votacion → cerrada | automática (`cierra_en`) o administrador; irreversible | ni emisión ni voto |
| cerrada → escrutada | administrador | se publica la urna, el recuento, los contadores y el acta |
| escrutada → archivada | administrador | se destruye o archiva offline la clave privada; se aplica retención |

La **ventana de emisión es anterior a la de voto** (p. ej. 48 h antes): así las horas de emisión no se pueden correlacionar con las de voto (R-05).

### 5.2 Primitiva: RSA ciego (RFC 9474)

- Variante propuesta: **RSABSSA-SHA384-PSS-Randomized** **[A CONFIRMAR]** (nombre exacto, hash, MGF1 y longitud de sal en el RFC).
- Módulo RSA: **3072 bits** propuesto; mínimo 2048 **[A CONFIRMAR; decisión de Fase 2]**.
- El cliente genera `nonce` de 32 bytes aleatorios; mensaje a firmar: `"PANRAP-v1" ‖ convocatoria_id ‖ nonce`. Con la variante *Randomized*, el cliente conserva además el prefijo aleatorio que el RFC añade.
- `token_id = SHA-256(mensaje firmado final)` (incluye el prefijo si lo hay). Se usa el mensaje, no la firma.
- El token **no contiene la opción de voto**: solo autoriza un voto. La opción viaja aparte.

### 5.3 Emisión (autenticada)

1. El cliente se autentica con su credencial (módulo del §6) → el Emisor obtiene `persona_ref`.
2. El cliente calcula `blinded_msg` (RFC `Blind`) y lo envía.
3. El Emisor comprueba: convocatoria en `emision` o `votacion`; persona registrada; `len(blinded_msg)` = longitud del módulo y valor menor que `n` **[A CONFIRMAR]**.
4. **Una sola emisión por persona:**
   - no hay emisión previa → firma (`BlindSign`), guarda `(convocatoria_id, persona_ref, SHA-256(blinded_msg), blind_sig)` y devuelve `blind_sig`;
   - hay emisión previa con el **mismo** `blinded_msg` → devuelve la **misma** `blind_sig` (reintento idempotente: si se perdió la respuesta, el usuario no queda "quemado");
   - hay emisión previa con **otro** `blinded_msg` → `409`.
5. El cliente ejecuta `Finalize` y guarda `(mensaje, firma)`. Nada de esto sale de su dispositivo hasta votar.

Una petición inválida **no consume** la emisión (cierra C3).

### 5.4 Voto (anónimo, sin credenciales)

1. El cliente envía `{mensaje, firma, opcion}` por una petición **sin cookies ni identificación**, con un retraso aleatorio respecto a la emisión (jitter configurable).
2. La Urna comprueba: convocatoria en `votacion`; formato; `opcion` ∈ opciones; firma válida bajo la clave pública de **esa** convocatoria.
3. Inserta `(convocatoria_id, token_id, opcion, mensaje, firma)`. Si la clave primaria ya existe → `409` (token gastado). La inserción es la comprobación: no se hace "mirar y luego insertar".
4. Responde `201` con `token_id` (recibo).

### 5.5 Cierre y escrutinio

1. Al cerrar se congela la urna y se compacta el almacenamiento (R-12).
2. Se publica la **urna completa ordenada por `token_id`** (no por orden de llegada), el recuento por opción y los contadores.
3. Un **verificador independiente** (script que solo usa la clave pública y la urna publicada) comprueba: firmas válidas, `token_id` únicos, opciones válidas, recuento. Es parte del entregable (AC-10).
4. El acta (PDF) incluye: parámetros de la convocatoria, modo y nivel de garantía, recuento, contadores, SHA-256 de la urna y del texto votado.

### 5.6 Propiedad de ceguera

El Emisor solo ve `blinded_msg` y `blind_sig`; la Urna solo ve `(mensaje, firma)`. Por la propiedad de ceguera del protocolo **[A CONFIRMAR en §Security Considerations del RFC]**, aunque ambos se unan no pueden enlazar una emisión con un token a partir de esos datos. La correlación solo es posible por metadatos (tiempo, red), de ahí R-05.

## 6. Elegibilidad modular (D2)

La capa de voto solo necesita una afirmación: *"esta persona es elegible, una vez, en esta convocatoria"*. Cómo se llega a ella cambia según el municipio. Un municipio con padrón lo usa; uno sin padrón usa otro modo y el sistema lo declara.

### 6.1 Contrato del módulo

```python
class ProveedorElegibilidad(Protocol):
    modo: str                                    # 'padron' | 'presencial' | 'aval' | 'eid'
    def nivel_garantia(self, cfg) -> str: ...    # 'alta' | 'media' | 'baja'
    def registrar(self, convocatoria_id, datos) -> str: ...      # -> persona_ref
    def autenticar(self, convocatoria_id, credencial) -> str | None: ...  # -> persona_ref o None
    def contadores(self, convocatoria_id) -> dict: ...  # registrados, censo_declarado
```

- `persona_ref = HMAC-SHA256(secreto_de_convocatoria, identificador_estable)`: seudónimo distinto en cada convocatoria, no enlazable entre ellas.
- Un módulo **no** conoce tokens ni votos.
- La configuración (modo y parámetros) es de despliegue, fuera del repo.

### 6.2 Modos iniciales

| Modo | Qué se verifica | Garantía | Amenazas propias | Parámetros |
|---|---|---|---|---|
| **`padron`** | la persona figura en una lista cargada por el ayuntamiento | **alta** si la activación llega por canal de confianza (postal o presencial); **media** si por correo o SMS | un identificador (DNI, etc.) es adivinable: **no basta para autenticar**; exige un secreto de activación entregado por el canal; la lista se guarda como hash salado y se borra tras la convocatoria | lista importada, canal de activación |
| **`presencial`** | un registrador municipal verifica a la persona en persona con criterios del municipio y le entrega un código de un solo uso (papel o QR) | **media** (depende del registrador) | registrador deshonesto (R-07) | roles de registrador, tope diario, doble registrador opcional |
| **`aval`** | K personas ya registradas avalan a la persona | **baja** | anillos de colusión; el grafo de avales es un dato personal sensible | K (por defecto 3), tope de avales por persona A (por defecto 5), sin avales recíprocos, semilla inicial dada de alta por registrador, el grafo se borra tras la convocatoria |
| **`eid`** | identidad digital nacional o similar, vía OIDC | la que declare el proveedor | el proveedor ve que la persona accede a la convocatoria (no su voto); no existe en todos los países | proveedor, nivel mínimo aceptado |

### 6.3 Reglas comunes

- **Un modo por convocatoria** (K10). Mezclar modos permitiría que una persona se registre dos veces.
- La convocatoria **publica**: modo, nivel de garantía, registradores (si los hay), censo declarado (si existe) y contadores.
- Los resultados deben leerse con ese nivel de garantía: una convocatoria de garantía *baja* no es comparable con una de *alta*.
- Añadir un modo nuevo no debe tocar la Emisión ni la Urna.

## 7. Modelo de datos

Dos almacenes **separados** (bases o esquemas distintos, sin claves foráneas entre ellos). `PRAGMA foreign_keys = ON` en cada conexión.

```sql
-- ===== Almacén A: identidad y emisión (nunca contiene votos) =====
CREATE TABLE convocatorias (
  id                TEXT PRIMARY KEY,                -- UUID
  propuesta_id      INTEGER NOT NULL,
  titulo            TEXT NOT NULL,
  texto_sha256      TEXT NOT NULL,
  opciones_json     TEXT NOT NULL,                   -- ["a_favor","en_contra","abstencion"]
  modo_elegibilidad TEXT NOT NULL CHECK (modo_elegibilidad IN ('padron','presencial','aval','eid')),
  nivel_garantia    TEXT NOT NULL CHECK (nivel_garantia IN ('alta','media','baja')),
  censo_declarado   INTEGER,                         -- NULL si no hay padrón
  emision_abre_en   TEXT NOT NULL,
  voto_abre_en      TEXT NOT NULL,
  cierra_en         TEXT NOT NULL,
  estado            TEXT NOT NULL CHECK (estado IN
                    ('borrador','programada','emision','votacion','cerrada','escrutada','archivada')),
  emisor_pub_pem    TEXT NOT NULL,
  emisor_pub_sha256 TEXT NOT NULL
  -- la clave PRIVADA no está en la base (ver §8)
);

CREATE TABLE personas (
  convocatoria_id TEXT NOT NULL REFERENCES convocatorias(id),
  persona_ref     TEXT NOT NULL,
  alta_por        TEXT,                              -- registrador (modo presencial) o NULL
  PRIMARY KEY (convocatoria_id, persona_ref)
);

CREATE TABLE emisiones (
  convocatoria_id    TEXT NOT NULL,
  persona_ref        TEXT NOT NULL,
  blinded_msg_sha256 TEXT NOT NULL,
  blind_sig          BLOB NOT NULL,
  PRIMARY KEY (convocatoria_id, persona_ref),
  FOREIGN KEY (convocatoria_id, persona_ref) REFERENCES personas(convocatoria_id, persona_ref)
);                                                   -- sin marcas de tiempo

-- ===== Almacén B: urna (nunca contiene personas) =====
CREATE TABLE convocatorias_pub (                     -- copia de solo lectura de lo público
  id TEXT PRIMARY KEY, opciones_json TEXT NOT NULL, emisor_pub_pem TEXT NOT NULL,
  voto_abre_en TEXT NOT NULL, cierra_en TEXT NOT NULL, estado TEXT NOT NULL
);

CREATE TABLE votos (
  convocatoria_id TEXT NOT NULL REFERENCES convocatorias_pub(id),
  token_id        BLOB NOT NULL,                     -- SHA-256 del mensaje firmado
  opcion          TEXT NOT NULL,
  mensaje         BLOB NOT NULL,
  firma           BLOB NOT NULL,
  PRIMARY KEY (convocatoria_id, token_id)
) WITHOUT ROWID;                                     -- sin orden de inserción recuperable
```

**Desaparecen** del diseño actual: `votos.usuario_id`, `votos.firma_ec`, `solicitudes_firma` (única por usuario de por vida, C2) y la verificación ECDSA de voto identificado (C5, C6).

## 8. Claves

- Una clave RSA **por convocatoria**, generada por el Emisor al pasar a `programada`.
- La clave privada vive **fuera de la base y de git**: archivo con permisos `0600` (o KMS/HSM si existe) en una ruta de despliegue; copia de seguridad offline y cifrada.
- Persiste entre reinicios y entre procesos (cierra C7); un cambio de clave durante una convocatoria invalida tokens y se trata como incidente.
- Tras `escrutada`: se destruye, o se archiva offline si se necesita auditar emisiones; **nunca** se reutiliza en otra convocatoria.
- `emisor_pub_sha256` se publica en el acta y en la convocatoria.

## 9. API (contrato v0)

Cuerpos JSON; datos binarios en base64url. Errores uniformes: `{"error": "<codigo>"}`. Validación con modelos tipados; tamaño máximo de cuerpo; CORS restringido; TLS obligatorio. Sin límites de tasa persistidos con IP.

| Método y ruta | Auth | Petición | Respuesta | Errores |
|---|---|---|---|---|
| `GET /convocatorias` y `/convocatorias/{id}` | no | — | parámetros públicos: opciones, ventanas, modo, nivel de garantía, clave pública, contadores | 404 |
| `POST /convocatorias/{id}/elegibilidad/...` | según módulo | según módulo | credencial | 400, 403 |
| `POST /convocatorias/{id}/emision` | **credencial** | `{blinded_msg}` | `200 {blind_sig}` | 400 formato, 401 sin credencial, 403 no elegible, 409 emisión previa con otro `blinded_msg` o convocatoria no abierta |
| `POST /convocatorias/{id}/votos` | **ninguna** | `{mensaje, firma, opcion}` | `201 {token_id}` | 400 inválido, 409 token gastado o convocatoria no abierta |
| `POST /convocatorias/{id}/cerrar` | administrador | — | 200 | 403, 409 |
| `GET /convocatorias/{id}/urna` | no, solo si `cerrada` o después | — | votos ordenados por `token_id` | 409 si abierta |
| `GET /convocatorias/{id}/escrutinio` | no, solo tras cierre | — | recuento y contadores | 409 |
| `POST /convocatorias/{id}/acta` | administrador | — | acta PDF | 403, 409 si no `escrutada` |

Las rutas antiguas `/votar`, `/validar-identidad` y `/propuestas/{id}/ejecutar-mandato` se sustituyen por las anteriores.

## 10. Criterios de aceptación (cada uno es un test)

| ID | Criterio | Cierra |
|---|---|---|
| AC-01 | Segunda emisión con `blinded_msg` distinto → 409; con el mismo → 200 y la misma `blind_sig` | C2 |
| AC-02 | Sin credencial → 401; persona no elegible → 403; sin efectos en la base | C3 |
| AC-03 | Voto con token válido → 201; el mismo token otra vez, con cualquier opción → 409; 50 peticiones concurrentes con el mismo token → exactamente 1 aceptada | C1 |
| AC-04 | Token firmado con la clave de otra convocatoria → 400 | — |
| AC-05 | Firma alterada, mensaje alterado, longitudes incorrectas, opción no listada, campos extra o cuerpo vacío → 400 (nunca 500) | A3 |
| AC-06 | Con N emisiones reales (cliente RSABSSA) los N `token_id` son distintos (propiedad, N = 1000) | C1 |
| AC-07 | Ni el esquema ni los datos de la urna contienen `persona_ref`, `usuario_id`, IP ni marcas de tiempo (test sobre `PRAGMA table_info` y un volcado) | A5 |
| AC-08 | Dos ejecuciones con distinto orden de llegada producen la misma publicación; tabla `WITHOUT ROWID` | A5 |
| AC-09 | Tras cerrar, emisión y voto → 409; el recuento publicado es igual a la cuenta por opción | — |
| AC-10 | El verificador independiente acepta una urna íntegra y rechaza: voto sin firma válida, `token_id` duplicado, voto de otra convocatoria, opción inexistente | K3 |
| AC-11 | `votos ≤ emisiones ≤ registrados ≤ censo_declarado` (si existe), con test de propiedades; el endpoint público lo muestra | K4 |
| AC-12 | Credencial de otro modo → 403; cambiar de modo exige una convocatoria nueva | K10 |
| AC-13 | La clave del emisor persiste entre procesos y difiere entre convocatorias; no está en la base ni en git (escáner de secretos y `git grep`) | C7 |
| AC-14 | `blinded_msg` inválido → 400 **y no consume** la emisión; una petición válida posterior → 200 | C3 |
| AC-15 | El acta solo se genera con convocatoria `escrutada` y rol administrador, e incluye recuento, hash de la urna, modo y nivel | C8 |
| AC-16 | Modelos tipados en todas las entradas; claves foráneas activas en cada conexión; CORS restringido; límite de tamaño de cuerpo | A3 |
| AC-17 | Los vectores de prueba del RFC 9474 pasan en CI para la biblioteca elegida (cliente y servidor) | A1 |
| AC-18 | Cada convocatoria publica modo, nivel de garantía, registradores y contadores | K4 |

**Relación con los tests `xfail` actuales** (cada uno pasará a XPASS estricto cuando se corrija, y entonces se retira la marca):

| Test actual | Se resuelve con |
|---|---|
| `test_c1_token_final_distinto_por_usuario` | AC-06 |
| `test_c3_sin_credenciales` | AC-02 |
| `test_c3_m_blind_no_numerico_quema_usuario` | AC-14 |
| `test_c4_insert_anonimo_directo` | §7 (esquema nuevo) |
| `test_c7_clave_persistente` | AC-13 |
| `test_c8_mandato_aprobada` | AC-15 |
| `test_c4_votar_finalize` y los de `test_api.py` con contrato `usuario_id`/`firma_ec` | el contrato antiguo se elimina; sus sustitutos son AC-03 y AC-05 |

## 11. Preguntas abiertas (con valor por defecto)

| ID | Pregunta | Defecto propuesto |
|---|---|---|
| OQ-01 | ¿Re-votación o voto único e irrevocable? | voto único |
| OQ-02 | Resistencia a la compra y coerción (necesaria para uso vinculante) | fuera de v0; bloquea el uso vinculante |
| OQ-03 | ¿Una instancia por municipio o multi-municipio? | una instancia por municipio |
| OQ-04 | Reglas de quórum y mayoría | parámetros por convocatoria; hoy rige "mayoría de a favor" |
| OQ-05 | Retención y borrado de datos tras archivar | borrar identidades, avales y lista al archivar; conservar urna y acta |
| OQ-06 | Canales sin smartphone: puestos de voto asistidos, papel, SMS | fuera de v0; es un módulo de *canal*, distinto del de elegibilidad |
| OQ-07 | ¿Quién opera Emisor y Urna? | operadores distintos cuando haya uso real |
| OQ-08 | Atar la opción al token con una clave efímera (el mensaje incluye una clave pública efímera y el voto se firma con ella) para cerrar R-14 | no en v0 |

## 12. Trazabilidad con la auditoría

| Hallazgo | Tratamiento |
|---|---|
| C1 token idéntico para todos | nonce aleatorio de 256 bits y `token_id` único (§5.2) |
| C2 una firma por usuario de por vida | emisión única por (convocatoria, persona) |
| C3 emisión sin autenticación y que "quema" | §5.3, AC-02, AC-14 |
| C4 `/votar` roto y `usuario_id NOT NULL` | contrato nuevo y §7 |
| C5 dos arquitecturas incompatibles | solo voto anónimo; se elimina el voto identificado |
| C6 verificador ECDSA que no verifica | eliminado |
| C7 clave efímera | §8, AC-13 |
| C8 acta rota y sin recuento | AC-15 |
| A1 RSA de libro | RFC 9474 (RSABSSA) |
| A2 Schnorr ciego (ataque ROS) | descartado; `sandbox/blind_schnorr/` queda archivado, "no usar" |
| A3 entradas sin validar | AC-05, AC-16 |
| A5 metadatos que correlacionan | §5.1 (ventanas), §7 (`WITHOUT ROWID`, sin marcas de tiempo), AC-07/08 |
| A6 frontend de prueba | cliente de referencia nuevo con vectores del RFC |

## 13. Investigación necesaria antes del Plan

Para cada biblioteca candidata de RFC 9474 (Python para el servidor y JavaScript para el cliente):

1. URL de origen, versión, fecha de la última versión, licencia compatible con AGPL-3.0.
2. ¿Pasa los vectores de prueba del RFC? Se ejecutan y se pega la salida.
3. Mantenimiento y base de usuarios; `pip-audit` o `npm audit` limpios.
4. Si no se puede verificar algo, se escribe **NO VERIFICADO**; no se supone.

**Entregable:** `02-investigacion-rfc9474.md` en esta carpeta, con las comprobaciones de los puntos marcados **[A CONFIRMAR]**.

## Historial

- 2026-10-26: motor sustituido por Blind Schnorr (ver `03-motor-blind-schnorr.md`).
- 2026-10-26: v0, redactada por Claude. Pendiente de revisión de Pedro (D3 y OQ-01…08).
