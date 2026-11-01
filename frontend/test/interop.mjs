// Recalcula con el núcleo JS los vectores generados por Python (tests/test_cliente_js.py).
import { readFileSync } from 'node:fs';
import { blindar } from '../src/voto_core.mjs';

const vectores = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const salida = vectores.map((v) => {
  const c = blindar({ Y_hex: v.Y_hex, R_hex: v.R_hex, conv_id: v.conv_id, opcion: v.opcion, a_hex: v.a_hex, b_hex: v.b_hex });
  const sp = c.finalizar(v.s_hex);
  let errorS = null;
  try { c.finalizar(v.s_ajena_hex); } catch (e) { errorS = e.message; }
  return { R_prima_hex: c.R_prima_hex, e_hex: c.e_hex, s_prima_hex: sp, error_s_ajena: errorS };
});
console.log(JSON.stringify(salida));
