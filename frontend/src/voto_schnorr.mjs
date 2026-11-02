// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Flujo de votación del navegador contra la API (rutas relativas: se sirve desde /ui del mismo servidor).
import { blindar, hexABytes, verificarToken } from './voto_core.mjs';
import { firmaCheckpointValida, hashHoja, hojaVoto, verificarCamino } from './registro.mjs';

async function pedir(fetchFn, url, opciones) {
  const resp = await fetchFn(url, opciones);
  let datos = {};
  try { datos = await resp.json(); } catch { /* cuerpo no JSON */ }
  if (!resp.ok) {
    const detalle = typeof datos.detail === 'string' ? datos.detail : resp.statusText;
    throw new Error(`${detalle} (HTTP ${resp.status})`);
  }
  return datos;
}

const post = (fetchFn, url, cuerpo) => pedir(fetchFn, url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(cuerpo),
});

export const listarConvocatorias = (base = '', fetchFn = globalThis.fetch) =>
  pedir(fetchFn, `${base}/convocatorias`);

export const cargarConvocatoria = (conv_id, base = '', fetchFn = globalThis.fetch) =>
  pedir(fetchFn, `${base}/convocatorias/${encodeURIComponent(conv_id)}`);

/** Envía el token ya firmado. Se separa para poder reintentar si falla solo este último paso. */
export async function enviarVoto(conv_id, token, base = '', fetchFn = globalThis.fetch) {
  return post(fetchFn, `${base}/convocatorias/${encodeURIComponent(conv_id)}/votos`, token);
}

/**
 * Emite el token con firma ciega y vota. No envía el id de sesión con el voto.
 * Si falla solo el envío, el error lleva `.token` para reintentar con enviarVoto().
 */
export async function flujoVoto(conv_id, credencial, opcion, base = '', fetchFn = globalThis.fetch) {
  const conv = await cargarConvocatoria(conv_id, base, fetchFn);
  if (!['emision', 'votacion'].includes(conv.estado)) throw new Error(`La convocatoria no está abierta (${conv.estado})`);
  if (!conv.opciones.includes(opcion)) throw new Error('Opción no válida para esta convocatoria'); // antes de gastar la emisión
  const ruta = `${base}/convocatorias/${encodeURIComponent(conv_id)}/emision`;
  const inicio = await post(fetchFn, `${ruta}/inicio`, { credencial });
  const cegado = blindar({ Y_hex: conv.emisor_pub_hex, R_hex: inicio.R, conv_id, opcion });
  const fin = await post(fetchFn, `${ruta}/fin`, { sesion: inicio.sid, e: cegado.e_hex });
  const token = { opcion, r_prima: cegado.R_prima_hex, s_prima: cegado.finalizar(fin.s) };
  try {
    await enviarVoto(conv_id, token, base, fetchFn);
  } catch (err) {
    err.token = token;
    throw err;
  }
  return { mensaje: 'Voto registrado', opcion, token };
}

/** Comprobante OPCIONAL: solo contiene lo necesario para localizar tu voto en la urna (nunca tu credencial). */
export const crearComprobante = (conv_id, token) => ({
  tipo: 'pan-rap-comprobante', version: 1, convocatoria_id: conv_id,
  opcion: token.opcion, r_prima: token.r_prima, s_prima: token.s_prima,
});

export function validarComprobante(c) {
  const hex = (v, bytes) => typeof v === 'string' && v.length === bytes * 2 && /^[0-9a-f]+$/i.test(v);
  if (!c || c.tipo !== 'pan-rap-comprobante' || c.version !== 1 || typeof c.convocatoria_id !== 'string'
    || typeof c.opcion !== 'string' || !hex(c.r_prima, 33) || !hex(c.s_prima, 32)) {
    throw new Error('El comprobante no tiene el formato esperado');
  }
  return c;
}

/**
 * Comprueba, SIN fiarse del servidor más de lo necesario, que tu voto consta en un checkpoint firmado:
 * 1) tu token es válido para la convocatoria; 2) su hoja está en la raíz Merkle del checkpoint de su lote;
 * 3) el checkpoint lo firmó la clave del registro. Si no pasas logPubEsperada, la clave se toma del servidor
 * (y se avisa). Devuelve { ok, pendiente, pasos:[{ok,texto}], advertencias:[] }.
 */
export async function verificarMiVoto(comprobante, { base = '', fetchFn = globalThis.fetch, logPubEsperada = '' } = {}) {
  const c = validarComprobante(comprobante);
  const pasos = [];
  const advertencias = [];
  const conv = await cargarConvocatoria(c.convocatoria_id, base, fetchFn);
  const tokenOk = verificarToken({ Y_hex: conv.emisor_pub_hex, conv_id: c.convocatoria_id, opcion: c.opcion,
    r_prima_hex: c.r_prima, s_prima_hex: c.s_prima });
  pasos.push({ ok: tokenOk, texto: 'La firma de tu token es válida para esta convocatoria' });
  if (!tokenOk) return { ok: false, pendiente: false, pasos, advertencias };
  let inclusion;
  try {
    inclusion = await pedir(fetchFn, `${base}/convocatorias/${encodeURIComponent(c.convocatoria_id)}/registro/inclusion?r_prima=${c.r_prima}`);
  } catch (e) {
    if (/HTTP 404/.test(e.message)) {
      advertencias.push('Tu voto aún no está sellado en ningún checkpoint. Se sella cada cierto número de votos y al cerrar la convocatoria: vuelve a comprobarlo más tarde.');
      return { ok: false, pendiente: true, pasos, advertencias };
    }
    throw e;
  }
  const cp = inclusion.checkpoint;
  const pub = (logPubEsperada || '').trim() || conv.log_pub_hex;
  if (!logPubEsperada) advertencias.push('La clave del registro se tomó del propio servidor. Compárala con la que se anunció antes de abrir la votación, o escríbela en el campo opcional.');
  const caminoOk = cp.n === inclusion.n && verificarCamino(hashHoja(hojaVoto(c.r_prima, c.s_prima, c.opcion)),
    inclusion.indice, inclusion.n, inclusion.camino.map(hexABytes), hexABytes(cp.root));
  pasos.push({ ok: caminoOk, texto: `Tu voto está en el checkpoint nº ${cp.seq} (${cp.n} votos sellados)` });
  const firmaOk = firmaCheckpointValida(pub, c.convocatoria_id, cp);
  pasos.push({ ok: firmaOk, texto: 'Ese checkpoint está firmado por la clave del registro' });
  return { ok: tokenOk && caminoOk && firmaOk, pendiente: false, pasos, advertencias };
}
