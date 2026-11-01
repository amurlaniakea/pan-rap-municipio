// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Flujo de votación del navegador contra la API (rutas relativas: se sirve desde /ui del mismo servidor).
import { blindar } from './voto_core.mjs';

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
  return { mensaje: 'Voto registrado', opcion };
}
