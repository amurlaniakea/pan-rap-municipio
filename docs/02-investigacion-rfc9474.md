---
title: PAN-RAP Municipio — Investigación RFC 9474 y bibliotecas
created: 2026-10-26
updated: 2026-10-26
type: investigacion
status: v1
tags: [pan-rap-municipio, sdd, criptografia, rfc9474]
sources: ["RFC 9474 (rfc-editor.org/rfc/rfc9474.html)", "github.com/cloudflare/blindrsa-ts", "docs.rs/blind-rsa-signatures"]
---

# Investigación RFC 9474 y bibliotecas (2026-10-26)

Resuelve los puntos **[A CONFIRMAR]** de `01-spec-v0.md`. Todo lo marcado como *probado* se ejecutó en un entorno aislado de Claude; lo que no pude comprobar figura como **NO VERIFICADO**. Esta investigación no sustituye a la auditoría criptográfica externa (Fase 6).

## 1. Resumen

| Pregunta | Resultado |
|---|---|
| ¿Existe la variante propuesta y con qué parámetros? | Sí: **RSABSSA-SHA384-PSS-Randomized**: SHA-384, MGF1 con SHA-384, sal de 48 bytes, relleno aleatorio de 32 bytes (RFC §4.1 y §5). Es una de las dos variantes RECOMENDADAS. |
| ¿Tamaño de módulo? | El RFC **no fija mínimo**; sus vectores usan 4096 bits. Elegido y probado: **3072**. |
| ¿La firma se verifica con herramientas estándar? | Sí: es una firma RSASSA-PSS normal (RFC §4.5). Probado con `cryptography` de Python. |
| ¿Hay ceguera? | Demostrada para las variantes *Randomized* (Lysyanskaya 2022, citada en RFC §7), con condiciones: ver §2. |
| ¿Cliente JS? | **`@cloudflare/blindrsa-ts` 0.4.6** (Apache-2.0): pasa los vectores del RFC en su suite y es interoperable con un servidor Python (probado). |
| ¿Servidor Python? | **No encontré biblioteca dedicada.** El servidor solo necesita BlindSign (una exponenciación RSA con comprobación) y la verificación PSS estándar. Validado contra los 4 vectores del RFC y en interoperabilidad. |
| ¿Rendimiento? | ~32 ms por firma (RSA-3072, CRT + cegado) y ~0,5 ms por verificación en Python, en la máquina de pruebas. |

## 2. Lo que dice el RFC 9474 (puntos relevantes)

| Tema | Hallazgo | Sección |
|---|---|---|
| Estatus | Es **Informational** (IRTF/CFRG), "no es un estándar". | §1 |
| Variantes | Cuatro: PSS/PSSZERO × Randomized/Deterministic. RECOMENDADAS: PSS-Randomized y PSSZERO-Randomized. | §5 |
| Mensaje | `PrepareRandomize` antepone 32 bytes aleatorios; el mensaje de la aplicación es el resto. El verificador debe quitar el prefijo. | §4.1, §4.5 |
| BlindSign | `RSASP1` + comprobación `RSAVP1(s) = m` (contra fallos). Error "message representative out of range" si el valor no está en [0, n−1]. | §4.3 |
| Finalize | Exige `len(blind_sig)` = longitud del módulo y verifica la firma antes de devolverla. | §4.4 |
| Claves | **No reutilizar** la clave para otro protocolo ni para otra variante de codificación. Generación recomendada: FIPS 186-5. | §6.2 |
| Canales laterales | El servidor debe aplicar mitigaciones (p. ej. cegado RSA) y comprobar el resultado de la firma. | §7.1 |
| Entropía del mensaje | Un firmante malicioso con una clave inválida puede aprender de mensajes de baja entropía. Condiciones: clave demostrablemente honesta, o componente de alta entropía en el mensaje. Las variantes *Randomized* inyectan esa entropía. | §7.3 |
| Aleatoriedad | Sal, prefijo y factor de cegado deben salir de un CSPRNG y **no deben poder ser aportados por el cliente** desde fuera de la biblioteca. | §7.4 |
| Sustitución de claves | RSA permite ataques de sustitución: el verificador debe usar la clave pública esperada del emisor. | §7.5 |
| Post-cuántico | No es post-cuántico. | §7.7 |
| Seguridad | One-more-forgery: tras *n* interacciones nadie produce *n+1* firmas sobre mensajes distintos. Ceguera demostrada para las variantes con `PrepareRandomize`. | §7 |

**Consecuencias para la Spec:** clave única y verificable por todos (§5.6 de la Spec), variante *Randomized*, nonce propio de 256 bits como defensa en profundidad, clave por convocatoria, cegado RSA en el Emisor.

## 3. Bibliotecas

| Lenguaje | Biblioteca | Estado | Notas |
|---|---|---|---|
| JavaScript / TypeScript (cliente) | **`@cloudflare/blindrsa-ts` 0.4.6** | Último commit 2026-10-24 (`1309019`). Licencia **Apache-2.0**. Usa WebCrypto; depende de `sjcl` 1.0.9. `npm audit --omit=dev`: **0 vulnerabilidades**. | Su suite carga los vectores del RFC 9474 (`test/testdata/test_vectors_rfc9474.json`). Declara `engines: node >=24`; mis pruebas corrieron en Node 22 sin problema. Licencia compatible con AGPL-3.0 según la guía habitual de la FSF (**NO VERIFICADO** aquí). |
| Python (servidor) | **ninguna dedicada encontrada** | — | Se propone usar `cryptography` para la verificación PSS y una función BlindSign mínima (Anexo A). |
| Rust | `blind-rsa-signatures` (jedisct1; coautor del RFC) | La página de docs.rs consultada muestra la versión 0.15.0, licencia MIT, dependiente de `rsa ^0.8.1`. | No comprobé versiones posteriores. Recuerdo un aviso de canal lateral de tiempo (Marvin) sobre el crate `rsa`; **NO VERIFICADO**: ejecutar `cargo audit` antes de considerarla. |
| Go | CIRCL (`blindsign/blindrsa`) | Solo vi páginas de *forks* en pkg.go.dev. | Repositorio oficial **NO VERIFICADO**. |

## 4. Pruebas ejecutadas (evidencia)

1. **Suite de `blindrsa-ts`** (`npm ci && npm test`, vitest 4.0.18): `test/blindrsa.test.ts` ✓ (17 tests) y `test/partially_blindrsa.test.ts` ✓ (26 tests). La salida que conservé mostraba esos dos archivos en verde; **no vi el resumen final** de la ejecución.
2. **Servidor Python contra los 4 vectores oficiales** (`check_vectors.py`): para cada variante, `blind_sig` calculado = el del RFC, `sig` desenmascarada = la del RFC y la firma verifica con RSASSA-PSS de `cryptography` (sal 48 o 0 según variante). Resultado: **4/4 correctos**.
3. **Interoperabilidad cliente JS ↔ servidor Python**, clave RSA-3072: el cliente JS (`RSABSSA.SHA384.PSS.Randomized`) prepara, ciega y, tras la firma ciega del servidor Python, desenmascara 20 tokens. La urna (Python) verifica los 20 con RSASSA-PSS estándar. Resultado: **20/20 válidos**.
4. **Pruebas negativas** (misma ejecución): mensaje alterado → rechazado; firma alterada → rechazada; clave de otra convocatoria → rechazada; segundo gasto del mismo `token_id` → rechazado por la clave primaria (20/20); `token_id` únicos; ningún valor en común entre lo que ve el Emisor (`blinded_msg`, `blind_sig`) y lo que ve la Urna (`mensaje`, `firma`).
5. **Entradas inválidas en el Emisor:** longitud incorrecta → rechazada; valor ≥ n → rechazado.
6. **Rendimiento** (Python, RSA-3072, misma máquina): `pow(m, d, n)` 102 ms; CRT 32 ms; CRT + cegado RSA 32 ms por firma; verificación pública ~0,5 ms. Con 26 000 votantes, 32 ms por firma suponen unos 14 minutos de CPU repartidos en la ventana de emisión.

## 5. Recomendación

1. **Cliente:** `@cloudflare/blindrsa-ts` fijada por versión y `package-lock`, y **vendorizada** (copia con su hash) para que el cliente servido no cambie sin control.
2. **Servidor:** BlindSign mínimo en Python con CRT, cegado RSA y comprobación de fallos (Anexo A), más verificación con `cryptography`. Validado con vectores e interoperabilidad. **Señalarlo para la Fase 6.** Si la auditoría lo desaconseja, mover el Emisor a un servicio con una biblioteca dedicada.
3. **Precisión de la Constitución (K6)** *pendiente de decisión de Pedro*: prohibir inventar primitivas o protocolos, y permitir implementar los pasos de un RFC con la aritmética de bibliotecas mantenidas si se valida con los vectores oficiales y se somete a auditoría.

## 6. Limitaciones (NO VERIFICADO)

- No ejecuté `cargo audit` ni revisé el crate Rust ni CIRCL oficial.
- No auditó nadie el código del Anexo A; las pruebas demuestran corrección funcional e interoperabilidad, **no** resistencia a canales laterales de tiempo en Python.
- Probé RSA-3072, no 4096. Los vectores del RFC usan 4096 bits.
- El resumen final de la suite de `blindrsa-ts` no lo vi (ver §4.1).
- Ejecuté todo en Node 22 y Python 3.12 con `cryptography` 46.0.6; el entorno de Pedro usa Python 3.14.

## Anexo A. BlindSign de referencia (servidor, Python)

```python
# Solo aritmética RSA + comprobación de fallos. Verificación de voto: RSASSA-PSS de 'cryptography'.
import secrets
from cryptography.hazmat.primitives import serialization

def blind_sign(key, blinded_msg: bytes) -> bytes:
    pn = key.private_numbers()
    n, e = pn.public_numbers.n, pn.public_numbers.e
    k = (n.bit_length() + 7) // 8
    if len(blinded_msg) != k:
        raise ValueError("longitud incorrecta")                      # 400
    m = int.from_bytes(blinded_msg, "big")
    if not (0 <= m < n):
        raise ValueError("representante fuera de rango")             # 400 (RFC 9474 §4.3)
    while True:                                                      # cegado RSA (RFC §7.1)
        r = secrets.randbelow(n - 2) + 2
        try:
            r_inv = pow(r, -1, n); break
        except ValueError:
            pass
    mm = (m * pow(r, e, n)) % n
    a = pow(mm % pn.p, pn.dmp1, pn.p)                                # CRT
    b = pow(mm % pn.q, pn.dmq1, pn.q)
    s = (b + ((pn.iqmp * (a - b)) % pn.p) * pn.q) % n
    s = (s * r_inv) % n
    if pow(s, e, n) != m:
        raise RuntimeError("fallo de firma")                         # RFC §4.3 y §7.1
    return s.to_bytes(k, "big")

PSS_PARAMS = dict(salt_length=48)   # PSS-Randomized: SHA-384, MGF1-SHA-384, sal 48 B
```

## Anexo B. Cómo reproducir

```bash
# Vectores del RFC y suite del cliente
git clone --depth 1 https://github.com/cloudflare/blindrsa-ts && cd blindrsa-ts
npm ci && npm test
# El archivo test/testdata/test_vectors_rfc9474.json trae los 4 vectores del RFC.
```

Para el servidor, repetir con Python las tres comprobaciones del §4 (vectores, interoperabilidad con el cliente y pruebas negativas). Estos scripts pasarán a ser tests de la Fase 2 (AC-17 y AC-06 de la Spec).

## Historial

- 2026-10-26: v1. Claude. Sustituye la tarea de investigación que se había encargado a Hermes.
