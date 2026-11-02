// Vota desde la UI y devuelve el estado del comprobante. Uso: node ui_comprobante.mjs <base> <conv> <credencial> <opción> <guardar:0|1>
import { cargarUI, leerEnlace } from './dom.mjs';

const [base, conv, credencial, opcion, guardar] = process.argv.slice(2);
const { $, esperar } = await cargarUI(base, `?conv=${conv}`);
const salida = { guardar_por_defecto: false };
await esperar(() => !$('panel').hidden);
salida.guardar_por_defecto = $('guardar').checked;
$('credencial').value = credencial;
if (guardar === '1') $('guardar').click();
[...$('opciones').querySelectorAll('button')].find((b) => b.dataset.opcion === opcion)?.click();
await esperar(() => /✅|❌/.test($('estado').textContent));
salida.estado = $('estado').textContent;
salida.paso = document.body.dataset.paso;
salida.hecho_visible = !$('hecho').hidden;
salida.panel_visible = !$('panel').hidden;
salida.bloque_comprobante_visible = !$('comp-bloque').hidden;
const texto = await leerEnlace($('descargar').getAttribute('href'));
salida.comprobante = texto ? JSON.parse(texto) : null;
console.log(JSON.stringify(salida));
process.exit(0);
