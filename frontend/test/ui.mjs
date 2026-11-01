// Ejecuta el bundle PUBLICADO (frontend/ui/voto.bundle.js) sobre el HTML que sirve el servidor, con un DOM de jsdom
// y fetch real contra el servidor. Uso: node ui.mjs <base> <conv_id|-> <credencial> <opción>
// Con conv_id = '-' no se pasa ?conv= y se vota eligiendo la convocatoria en la lista.
import { JSDOM } from 'jsdom';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const [base, conv, credencial, opcion] = process.argv.slice(2);
const url = `${base}/ui/${conv === '-' ? '' : `?conv=${conv}`}`;
const html = await (await fetch(url)).text();
const dom = new JSDOM(html, { url });
const nativo = globalThis.fetch;
Object.assign(globalThis, { window: dom.window, document: dom.window.document, location: dom.window.location });
globalThis.fetch = (u, o) => nativo(new URL(u, url).href, o);

const esperar = async (cond, ms = 8000) => {
  const fin = Date.now() + ms;
  while (Date.now() < fin) { if (cond()) return true; await new Promise((r) => setTimeout(r, 25)); }
  return false;
};
const $ = (id) => document.getElementById(id);
const botones = (id) => [...$(id).querySelectorAll('button')];
const salida = { csp: html.includes('Content-Security-Policy') };

await import(pathToFileURL(resolve('frontend/ui/voto.bundle.js')).href);   // ejecuta app.mjs como lo haría el navegador

if (conv === '-') {
  salida.lista = await esperar(() => botones('lista').length > 0) ? botones('lista').map((b) => b.textContent) : [];
  botones('lista')[0]?.click();
}
salida.cargada = await esperar(() => !$('panel').hidden);
salida.titulo = $('titulo').textContent;
salida.clave = $('clave').textContent.includes('Clave pública');
salida.opciones = botones('opciones').map((b) => b.textContent);
$('credencial').value = credencial;
botones('opciones').find((b) => b.textContent === opcion)?.click();
await esperar(() => /✅|❌|Introduce/.test($('estado').textContent));
salida.estado = $('estado').textContent;
salida.clase = $('estado').className;
console.log(JSON.stringify(salida));
process.exit(0);
