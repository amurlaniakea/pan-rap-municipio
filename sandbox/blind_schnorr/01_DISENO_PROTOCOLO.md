# Diseño del Protocolo Blind Schnorr (Fase 5)

## Objetivo
Migrar de Blind RSA a Blind Schnorr sobre Curvas Elípticas (ECC) para lograr firmas de 64 bytes, mayor velocidad y seguridad auditada mediante `@noble/curves`.

## Actores
- **Cliente (Votante)**: Ciega el mensaje, recibe la firma parcial, la descifra y la verifica.
- **Validador (Autoridad)**: Firma el dato cegado sin conocer el mensaje original ni poder vincular la firma final al proceso de cegado.

## Pasos del Protocolo (Bosquejo Inicial)
1. **Claves del Validador**: Par `(d, Q)` donde `Q = d * G` (G es el generador de la curva, ej. secp256k1).
2. **Cegado (Cliente)**:
   - Genera un nonce aleatorio `k` y calcula `R = k * G`.
   - Genera factores de cegado aleatorios `α` y `β`.
   - Calcula el punto cegado `R' = R + α * G + β * Q`.
   - Calcula el desafío cegado `e' = Hash(R', m) + β`.
   - Envía `e'` al validador.
3. **Firma (Validador)**:
   - Genera su propio nonce `k_v` y punto `R_v = k_v * G`. (Nota: El protocolo de cegado Schnorr requiere un ajuste específico para que el validador firme un desafío cegado. Refinaremos esto en la implementación).
   - *Alternativa estándar (Blind Schnorr de Chaum o variantes)*: El validador proporciona una firma sobre un compromiso, y el cliente lo ajusta. Documentaremos la variante exacta elegida aquí una vez probada.
4. **Descifrado (Cliente)**: El cliente ajusta la respuesta del validador usando `α` y `β` para obtener `(R, s)` válido para `m`.
5. **Verificación**: `s * G == R + e * Q` donde `e = Hash(R, m)`.

## Deudas y Limitaciones Conocidas (A completar)
- [ ] Validar que la librería `@noble/curves` exponga las primitivas necesarias sin workarounds inseguros.
- [ ] Garantizar que la generación de números aleatorios en el frontend sea criptográficamente segura (`crypto.getRandomValues`).
