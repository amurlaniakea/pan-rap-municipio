# 04 — Modelo de confianza (Fase 6a)

Este documento dice **qué garantiza** el prototipo y **qué no**. Sustituye cualquier afirmación más fuerte en otros documentos.

## Lo que la criptografía sí da

- **Ceguera de la firma.** En Blind Schnorr el emisor firma `e = e' + b` sin ver el mensaje (`PANRAP-v1|<convocatoria>|<opción>`) ni el token final `(R', s')`. A partir de lo que firma no puede reconstruir qué voto emitió cada persona.
- **Verificación pública.** Cualquiera con la clave pública `Y` de la convocatoria verifica cada voto sin claves privadas.
- **Un token, una opción, una convocatoria.** La firma cubre el mensaje; cambiar la opción o la convocatoria la invalida. Cada convocatoria firma con su propia clave (derivada de la maestra), así que un token de una convocatoria no vale en otra.
- **Sin doble gasto.** `PRIMARY KEY (convocatoria_id, r_prima)`.
- **Un token por persona del censo.** La emisión es transaccional: una persona solo recibe una firma (`emisiones`); si abandona antes de recibirla puede reintentar hasta 3 veces.

## Lo que NO garantiza

1. **Anonimato frente a quien opera el servidor.** Emisor y urna corren en el mismo proceso y con el mismo operador. La emisión es secuencial y cada voto llega después desde la misma red: IP, tiempos de llegada y logs permiten **correlacionar identidad y voto**. El anonimato depende de que el operador no registre ni cruce esos metadatos, o de separar emisor y urna en el futuro (mixnet, Tor, retardos aleatorios).
2. **Integridad frente al emisor.** El emisor posee la clave de firma y **puede fabricar votos válidos**. Solo se detecta parcialmente: `total_votos` no debe superar `emisiones_completadas`, pero puede sustituir los votos de quienes emitieron y no votaron.
3. **Compromiso durante la votación.** La urna se publica al cerrar; su hash no está firmado ni encadenado. No hay prueba de que no se añadieran o quitaran votos antes del cierre.
4. **Resistencia a la denegación de servicio.** Solo hay una sesión de emisión abierta por convocatoria (S1: protege frente al ataque ROS/Wagner). Una persona del censo puede ocupar la sesión hasta 10 s cada vez (con intentos limitados a 3).
5. **Un solo proceso.** El cerrojo S1 es `threading.Lock()` en memoria; ejecutar varios workers lo rompe. Usar `--workers 1`.
6. **Autenticación del votante.** La «credencial» es el identificador que figura en el censo. Quien la conozca puede emitir su token: no hay segundo factor.
7. **Administración.** Un único token compartido (`PANRAP_ADMIN_TOKEN`) da control total del ciclo de vida y del censo.

## Otros límites del prototipo

- Las fechas de la convocatoria no se aplican; el administrador cambia el estado a mano.
- Solo está implementado el modo de elegibilidad `padron`.
- Sin auditoría criptográfica externa (Fase 6b). La derivación de claves por convocatoria y el protocolo concreto deben ser revisados por terceros antes de cualquier uso real.
