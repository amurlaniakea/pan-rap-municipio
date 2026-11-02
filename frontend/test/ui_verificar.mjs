// Pulsa «Comprobar» en la UI para varios casos. Uso: node ui_verificar.mjs <base> <casos.json>
// casos.json: [{ "comprobante": <objeto|cadena>, "logpub": "<hex opcional>" }]
import { readFileSync } from 'node:fs';
import { cargarUI } from './dom.mjs';

const [base, ruta] = process.argv.slice(2);
const casos = JSON.parse(readFileSync(ruta, 'utf8'));
const { $, esperar } = await cargarUI(base);
const salida = [];
for (const caso of casos) {
  $('pegado').value = typeof caso.comprobante === 'string' ? caso.comprobante : JSON.stringify(caso.comprobante);
  $('logpub').value = caso.logpub || '';
  $('verificar').click();
  await esperar(() => $('resultado').querySelector('li.final, li.error'));
  await new Promise((r) => setTimeout(r, 50));
  salida.push([...$('resultado').querySelectorAll('li')].map((li) => ({ clase: li.className, texto: li.textContent })));
}
console.log(JSON.stringify(salida));
process.exit(0);
