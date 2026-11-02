// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Verificación en el navegador del registro de la urna: debe coincidir con registro.py (RFC 6962 + checkpoints firmados).
import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha2.js';
import { hexABytes } from './voto_core.mjs';

const enc = new TextEncoder();

function concat(...partes) {
  const out = new Uint8Array(partes.reduce((s, p) => s + p.length, 0));
  let pos = 0;
  for (const p of partes) { out.set(p, pos); pos += p.length; }
  return out;
}

const iguales = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/** Contenido de la hoja de un voto: r(33) ‖ s(32) ‖ len(opción) ‖ opción. */
export function hojaVoto(r_hex, s_hex, opcion) {
  const r = hexABytes(r_hex);
  const s = hexABytes(s_hex);
  const ob = enc.encode(opcion);
  if (r.length !== 33 || s.length !== 32 || ob.length > 255) throw new Error('voto con formato inválido');
  return concat(r, s, Uint8Array.of(ob.length), ob);
}

export const hashHoja = (datos) => sha256(concat(Uint8Array.of(0), datos));
const nodo = (izq, der) => sha256(concat(Uint8Array.of(1), izq, der));

function mayorPotenciaMenor(n) {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

/** Verifica un camino de inclusión RFC 6962 (el hermano más exterior va el último). */
export function verificarCamino(hoja, i, n, ruta, raiz) {
  const calc = (i, n, ruta) => {
    if (n === 1) return ruta.length === 0 ? hoja : null;
    if (ruta.length === 0) return null;
    const k = mayorPotenciaMenor(n);
    const resto = ruta.slice(0, -1);
    const ultimo = ruta[ruta.length - 1];
    if (i < k) {
      const sub = calc(i, k, resto);
      return sub === null ? null : nodo(sub, ultimo);
    }
    const sub = calc(i - k, n - k, resto);
    return sub === null ? null : nodo(ultimo, sub);
  };
  if (!Number.isInteger(i) || !Number.isInteger(n) || i < 0 || i >= n) return false;
  const calculada = calc(i, n, ruta);
  return calculada !== null && iguales(calculada, raiz);
}

export function mensajeCheckpoint(conv_id, cp) {
  return enc.encode(`PANRAP-CKPT-v1|${conv_id}|${cp.seq}|${cp.n}|${cp.root}|${cp.prev}|${cp.creado}`);
}

/** Firma ECDSA (DER) del servidor sobre SHA-256 del mensaje del checkpoint. Nunca lanza. */
export function firmaCheckpointValida(log_pub_hex, conv_id, cp) {
  try {
    const sig = secp256k1.Signature.fromDER(cp.firma);
    return secp256k1.verify(sig, sha256(mensajeCheckpoint(conv_id, cp)), log_pub_hex);
  } catch {
    return false;
  }
}
