import { secp256k1 } from './lib/noble/curves/secp256k1.js';
import { sha256 } from './lib/noble/hashes/sha2.js';

const CURVE_ORDER = secp256k1.CURVE.n;

function bytesToHex(b) {
  return Array.from(b).map((x) => x.toString(16).padStart(2, "0")).join("");
}
function hexToBytes(h) {
  return new Uint8Array(h.match(/.{1,2}/g).map((x) => parseInt(x, 16)));
}
function bytesToBigInt(b) {
  const hex = bytesToHex(b);
  return BigInt("0x" + hex);
}
function bigIntToBytes32(num) {
  const hex = num.toString(16).padStart(64, "0");
  return hexToBytes(hex);
}
function mod(a, b) {
  const r = a % b;
  return r >= 0n ? r : b + r;
}

async function flujoVoto(opcion, endpointInicio, endpointFin, endpointVoto) {
  const respInicio = await fetch(endpointInicio, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ convocatoria_id: "test" })
  });
  const dataInicio = await respInicio.json();
  if (!respInicio.ok) throw new Error("Inicio fallido: " + (dataInicio.detail || respInicio.statusText));

  const R_hex = dataInicio.R;
  const Y_hex = dataInicio.Y || dataInicio.public_key || R_hex; // respaldo
  const R_point = secp256k1.ProjectivePoint.fromHex(R_hex);

  // Generar cegado a, b
  const a_bytes = new Uint8Array(32);
  const b_bytes = new Uint8Array(32);
  crypto.getRandomValues(a_bytes);
  crypto.getRandomValues(b_bytes);
  const a = bytesToBigInt(a_bytes);
  const b = bytesToBigInt(b_bytes);

  // R' = R + a*G + b*Y
  const G = secp256k1.ProjectivePoint.BASE;
  const Y_point = secp256k1.ProjectivePoint.fromHex(Y_hex);
  const R_prima = R_point.add(G.multiply(a)).add(Y_point.multiply(b));

  // e' = H(R', m)
  const R_prima_bytes = R_prima.toRawBytes(true); // comprimido 33 bytes
  const m_str = `PANRAP-v1|test|${opcion}`;
  const m_bytes = new TextEncoder().encode(m_str);
  const combined = new Uint8Array(R_prima_bytes.length + m_bytes.length);
  combined.set(R_prima_bytes);
  combined.set(m_bytes, R_prima_bytes.length);
  const e_prima_bytes = sha256(combined);
  const e_prima = bytesToBigInt(e_prima_bytes);

  // e = e' + b
  const e = mod(e_prima + b, CURVE_ORDER);
  const e_hex = bytesToHex(bigIntToBytes32(e));

  const respFin = await fetch(endpointFin, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sesion: dataInicio.sid, e: e_hex })
  });
  const dataFin = await respFin.json();
  if (!respFin.ok) throw new Error("Fin fallido: " + (dataFin.detail || respFin.statusText));

  const s_bytes = hexToBytes(dataFin.s);
  const s_big = bytesToBigInt(s_bytes);
  const s_prima_big = mod(s_big + a, CURVE_ORDER);
  const s_prima_hex = bytesToHex(bigIntToBytes32(s_prima_big));

  const respVoto = await fetch(endpointVoto, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      opcion,
      R_prima: bytesToHex(R_prima_bytes),
      s_prima: s_prima_hex,
      sesion: dataInicio.sid
    })
  });
  const dataVoto = await respVoto.json();
  if (!respVoto.ok) throw new Error("Voto fallido: " + (dataVoto.detail || respVoto.statusText));
  return dataVoto;
}

window.flujoVoto = flujoVoto;
