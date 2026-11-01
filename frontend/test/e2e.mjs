// Vota contra un servidor real con el mismo flujo del navegador: node e2e.mjs <base> <conv> <credencial> <opcion>
import { flujoVoto } from '../src/voto_schnorr.mjs';

const [base, conv, credencial, opcion] = process.argv.slice(2);
try {
  console.log(JSON.stringify(await flujoVoto(conv, credencial, opcion, base)));
} catch (e) {
  console.log(JSON.stringify({ error: e.message, token_pendiente: Boolean(e.token) }));
  process.exit(1);
}
