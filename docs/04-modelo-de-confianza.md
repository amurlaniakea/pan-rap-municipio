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
3. **Compromiso durante la votación: parcial.** Desde la Fase 7 los votos se sellan por lotes en checkpoints firmados y encadenados (ver abajo). Sigue sin haber garantía sobre los votos todavía **sin sellar** (hasta `PANRAP_CHECKPOINT_CADA` votos o hasta el siguiente sellado manual) ni sobre un servidor que nadie observe.
4. **Resistencia a la denegación de servicio.** Solo hay una sesión de emisión abierta por convocatoria (S1: protege frente al ataque ROS/Wagner). Una persona del censo puede ocupar la sesión hasta 10 s cada vez (con intentos limitados a 3).
5. **Un solo proceso.** El cerrojo S1 es `threading.Lock()` en memoria; ejecutar varios workers lo rompe. Usar `--workers 1`.
6. **Autenticación del votante.** La «credencial» es el identificador que figura en el censo. Quien la conozca puede emitir su token: no hay segundo factor.
7. **Resistencia a la coacción.** El votante conoce `(R', s')`, que quedan en la urna pública: puede demostrar a un tercero cómo votó (compra o coacción de votos). Las firmas ciegas no son *receipt-free*.
8. **Administración.** Un único token compartido (`PANRAP_ADMIN_TOKEN`) da control total del ciclo de vida y del censo.

## Registro verificable de la urna (Fase 7)

Cada `PANRAP_CHECKPOINT_CADA` votos (por defecto 20), al cerrar y cuando el administrador llama a `POST /convocatorias/{id}/registro/sellar`, el servidor sella los votos nuevos en un **checkpoint**: `n` votos, raíz Merkle (RFC 6962) sobre las hojas `r' ‖ s' ‖ len ‖ opción` ordenadas por (lote, `r'`), hash del checkpoint anterior y firma con una clave de registro propia de la convocatoria (distinta de la de firma ciega). Los checkpoints son públicos en `GET /convocatorias/{id}/registro` y **no contienen votos, opciones ni tokens**.

Qué permite detectar, siempre que alguien haya **archivado los checkpoints durante la votación** (`scripts/observador.py`, en una máquina distinta y a ser posible varias, con `--log-pub` fijada antes de abrir):
- **Voto real retirado o modificado después de sellarse**: al cierre, `verificador_independiente.py` recalcula todas las raíces con los votos publicados y no coinciden.
- **Historias distintas para observadores distintos o reescritura posterior**: dos checkpoints firmados con la misma posición y contenido distinto son una prueba transferible de equivocación; un servidor que sirve menos checkpoints que los archivados, un retroceso.
- **Voto propio omitido**: cada votante puede pedir `GET /convocatorias/{id}/registro/inclusion?r_prima=…` y verificar su prueba contra la raíz firmada de su lote.

Qué **no** detecta ni impide:
- **Votos fabricados por el emisor** con la clave de firma: se sellarían igual que los reales (solo la comparación `total_votos` vs `emisiones_completadas` los acota).
- **Votos sin sellar**: un operador puede descartar los últimos votos antes del siguiente checkpoint. Reducir `PANRAP_CHECKPOINT_CADA` o sellar desde un cron acorta esa ventana, pero **revela más del orden de llegada** (dentro de un lote el orden es el de `r'`, no el de llegada).
- **Clave del registro sustituida**: si el observador acepta la clave que sirve el propio servidor, un servidor deshonesto puede firmar otra historia. La clave de registro debe fijarse por un canal independiente antes de abrir la votación.
- **Un solo observador comprometido o inexistente**: sin archivo externo, los checkpoints solo prueban coherencia interna.
- **Privacidad**: los checkpoints publican cuántos votos hay sellados en cada momento (participación parcial, no resultado).

## Comprobante opcional del votante

El votante puede pedir un comprobante (casilla **desactivada por defecto**) y comprobar en su navegador que su voto consta en un checkpoint firmado: token válido, camino de inclusión Merkle y firma ECDSA de la clave del registro. Qué implica:
- **Protege** frente a que el servidor omita o altere un voto ya sellado, siempre que el votante fije la clave del registro anunciada antes de abrir la votación (si la toma del propio servidor, la verificación solo prueba coherencia interna).
- **Facilita la coacción y la compra de votos**: el comprobante demuestra a un tercero cómo se votó. Sin él, el votante aún conoce `(R', s')` (están en la urna pública), pero la página no los pone a un clic. Por eso es opcional y viene desactivado.
- No cubre votos aún sin sellar: hasta el siguiente checkpoint la verificación responde «todavía no sellado».

## Otros límites del prototipo

- Las fechas de la convocatoria no se aplican; el administrador cambia el estado a mano.
- El cliente web es mínimo, sin auditoría ni pruebas en navegadores concretos. Quien sirva `/ui` puede cambiar el JavaScript: la garantía real depende de que el votante use un cliente cuyo hash coincida con `frontend/SHA256SUMS`.
- Solo está implementado el modo de elegibilidad `padron`.
- Sin auditoría criptográfica externa (Fase 6b). La derivación de claves por convocatoria y el protocolo concreto deben ser revisados por terceros antes de cualquier uso real.
