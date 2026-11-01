// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Núcleo puro del cliente Blind Schnorr (sin red ni DOM). Debe coincidir bit a bit con urna_schnorr.py:
//   m  = "PANRAP-v1|<convocatoria>|<opción>"            (UTF-8)
//   e' = SHA-256(T ‖ T ‖ R' ‖ Y ‖ m) mod q,  T = SHA-256("PANRAP-BSCHNORR-v1")
//   R' = R + a·G + b·Y ;  e = e' + b ;  s' = s + a
import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha2.js';

const Point = secp256k1.ProjectivePoint;
const N = secp256k1.CURVE.n;
const G = Point.BASE;
const T = sha256(new TextEncoder().encode('PANRAP-BSCHNORR-v1'));

export function bytesAHex(b) {
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
}

export function hexABytes(h) {
  if (typeof h !== 'string' || h.length % 2 !== 0 || !/^[0-9a-fA-F]*$/.test(h)) throw new Error('hex inválido');
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.slice(2 * i, 2 * i + 2), 16);
  return out;
}

const aBigInt = (bytes) => BigInt('0x' + (bytesAHex(bytes) || '0'));
const a32 = (n) => hexABytes(n.toString(16).padStart(64, '0'));

function concat(...partes) {
  const out = new Uint8Array(partes.reduce((s, p) => s + p.length, 0));
  let pos = 0;
  for (const p of partes) { out.set(p, pos); pos += p.length; }
  return out;
}

function escalarAleatorio() {
  for (;;) {
    const buf = new Uint8Array(64); // 512 bits reducidos mod q: sesgo despreciable
    globalThis.crypto.getRandomValues(buf);
    const k = aBigInt(buf) % N;
    if (k !== 0n) return k;
  }
}

function escalarDeHex(h, nombre) {
  const k = aBigInt(hexABytes(h));
  if (k <= 0n || k >= N) throw new Error(`${nombre} fuera de rango`);
  return k;
}

function campo(valor, nombre) {
  if (typeof valor !== 'string' || valor === '' || valor.includes('|')) {
    throw new Error(`${nombre} vacío, no textual o con el separador '|'`);
  }
  return valor;
}

export function mensaje(conv_id, opcion) {
  return new TextEncoder().encode(`PANRAP-v1|${campo(conv_id, 'convocatoria')}|${campo(opcion, 'opción')}`);
}

/**
 * Cega la sesión del emisor. a_hex y b_hex solo se pasan en pruebas con vectores fijos.
 * Devuelve { R_prima_hex, e_hex, finalizar(s_hex) -> s_prima_hex }.
 * finalizar() comprueba la respuesta del emisor (s·G = R + e·Y) y el token final antes de devolverlo.
 */
export function blindar({ Y_hex, R_hex, conv_id, opcion, a_hex, b_hex }) {
  if (typeof Y_hex !== 'string' || Y_hex.length !== 66) throw new Error('Y debe ser 33 bytes en hex');
  const Y = Point.fromHex(Y_hex);
  const R = Point.fromHex(R_hex);
  const m = mensaje(conv_id, opcion);
  const Y_bytes = Y.toRawBytes(true);
  for (;;) {
    const a = a_hex ? escalarDeHex(a_hex, 'a') : escalarAleatorio();
    const b = b_hex ? escalarDeHex(b_hex, 'b') : escalarAleatorio();
    const Rp = R.add(G.multiply(a)).add(Y.multiply(b));
    const Rp_bytes = Rp.toRawBytes(true);
    const ep = aBigInt(sha256(concat(T, T, Rp_bytes, Y_bytes, m))) % N;
    const e = (ep + b) % N;
    if (ep === 0n || e === 0n) {
      if (a_hex || b_hex) throw new Error('vector degenerado');
      continue; // probabilidad ~2^-256: se reintenta con otros a, b
    }
    return {
      R_prima_hex: bytesAHex(Rp_bytes),
      e_hex: bytesAHex(a32(e)),
      finalizar(s_hex) {
        const s = aBigInt(hexABytes(s_hex));
        if (s <= 0n || s >= N || !G.multiply(s).equals(R.add(Y.multiply(e)))) {
          throw new Error('Respuesta del emisor inválida');
        }
        const sp = (s + a) % N;
        if (sp === 0n || !G.multiply(sp).equals(Rp.add(Y.multiply(ep)))) {
          throw new Error('Token final inválido');
        }
        return bytesAHex(a32(sp));
      },
    };
  }
}
