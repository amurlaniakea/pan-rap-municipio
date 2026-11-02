// Vota contra un servidor real con el mismo flujo del navegador: node e2e.mjs <base> <conv> <credencial> <opcion>
import { flujoVoto } from '../src/voto_schnorr.mjs';

const [base, conv, credencial, opcion] = process.argv.slice(2);
try {
  const r = await flujoVoto(conv, credencial, opcion, base);
  console.log(JSON.stringify({ mensaje: r.mensaje, opcion: r.opcion }));   // nunca se imprime el token
} catch (e) {
  console.log(JSON.stringify({ error: e.message, token_pendiente: Boolean(e.token) }));
  process.exit(1);
}
