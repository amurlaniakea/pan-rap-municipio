// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Interfaz. Solo textContent (nunca innerHTML) y sin scripts ni estilos en línea (CSP estricta).
import { cargarConvocatoria, crearComprobante, enviarVoto, flujoVoto, listarConvocatorias, verificarMiVoto } from './voto_schnorr.mjs';

const $ = (id) => document.getElementById(id);
const ICONOS = { a_favor: '✔', si: '✔', en_contra: '✖', no: '✖', abstencion: '○' };
const AYUDA_CREDENCIAL = ' Comprueba que la has escrito exactamente igual (mayúsculas, números y guiones) o que no la has usado ya.';
let conv = null;
let tokenPendiente = null;

function paso(n) { document.body.dataset.paso = String(n); }

function estado(texto, clase = '') {
  const el = $('estado');
  el.textContent = texto;
  el.className = clase;
}

function enlaceDescarga(objeto) {
  const texto = JSON.stringify(objeto, null, 2);
  try {
    return URL.createObjectURL(new Blob([texto], { type: 'application/json' }));
  } catch {
    return `data:application/json;charset=utf-8,${encodeURIComponent(texto)}`;
  }
}

async function cargar() {
  const id = $('conv').value.trim();
  if (!id) return estado('Introduce el identificador de la convocatoria', 'error');
  try {
    conv = await cargarConvocatoria(id);
  } catch (e) {
    return estado(`No se pudo cargar: ${e.message}`, 'error');
  }
  $('titulo').textContent = conv.titulo;
  $('huella').textContent = `Huella del texto (SHA-256): ${conv.texto_sha256}`;
  $('clave').textContent = `Clave pública de la convocatoria: ${conv.emisor_pub_hex}`;
  const caja = $('opciones');
  caja.replaceChildren();
  for (const op of conv.opciones) {
    const b = document.createElement('button');
    const icono = document.createElement('span');
    const texto = document.createElement('span');
    b.type = 'button';
    b.className = 'btn';
    b.dataset.opcion = op;
    icono.className = 'icono';
    icono.textContent = ICONOS[op] || '●';
    texto.textContent = op.replaceAll('_', ' ');
    b.append(icono, texto);
    b.addEventListener('click', () => votar(op));
    caja.append(b);
  }
  $('hecho').hidden = true;
  $('panel').hidden = false;
  paso(2);
  estado(conv.estado === 'emision' || conv.estado === 'votacion' ? 'Convocatoria abierta' : `Convocatoria no abierta (${conv.estado})`);
}

function bloquear(valor) {
  document.querySelectorAll('#opciones .btn').forEach((b) => { b.disabled = valor; });
}

function mostrarExito(resultado, guardar) {
  $('panel').hidden = true;
  $('hecho').hidden = false;
  $('hecho-texto').textContent = `Tu voto «${resultado.opcion.replaceAll('_', ' ')}» se ha registrado de forma anónima. Ya puedes cerrar esta página.`;
  $('comp-bloque').hidden = !guardar;
  if (guardar) $('descargar').href = enlaceDescarga(crearComprobante(conv.id, resultado.token));
  else $('descargar').removeAttribute('href');
  paso(3);
}

async function votar(opcion) {
  const credencial = $('credencial').value.trim();
  if (!credencial) return estado('Introduce tu credencial', 'error');
  const guardar = $('guardar').checked;
  bloquear(true);
  estado('Firmando y enviando el voto…');
  try {
    const r = await flujoVoto(conv.id, credencial, opcion);
    mostrarExito(r, guardar);
    estado(`✅ ${r.mensaje}. Ya puedes cerrar esta página.`, 'ok');
  } catch (e) {
    if (e.token) {
      tokenPendiente = { token: e.token, guardar };
      $('reintentar').hidden = false;
      estado(`El token se firmó pero el envío falló: ${e.message}. Pulsa «Reintentar envío».`, 'error');
    } else {
      estado(`❌ ${e.message}${/Credencial/.test(e.message) ? AYUDA_CREDENCIAL : ''}`, 'error');
      bloquear(false);
    }
  }
}

async function reintentar() {
  try {
    await enviarVoto(conv.id, tokenPendiente.token);
    $('reintentar').hidden = true;
    mostrarExito({ opcion: tokenPendiente.token.opcion, token: tokenPendiente.token }, tokenPendiente.guardar);
    tokenPendiente = null;
    estado('✅ Voto registrado. Ya puedes cerrar esta página.', 'ok');
  } catch (e) {
    estado(`❌ ${e.message}`, 'error');
  }
}

function linea(clase, texto) {
  const li = document.createElement('li');
  li.className = clase;
  li.textContent = texto;
  $('resultado').append(li);
}

async function comprobar() {
  $('resultado').replaceChildren();
  let comprobante;
  try {
    comprobante = JSON.parse($('pegado').value);
  } catch {
    return linea('error', '❌ El texto pegado no es un comprobante válido (JSON).');
  }
  try {
    const r = await verificarMiVoto(comprobante, { logPubEsperada: $('logpub').value.trim() });
    for (const p of r.pasos) linea(p.ok ? 'ok' : 'error', `${p.ok ? '✅' : '❌'} ${p.texto}`);
    for (const a of r.advertencias) linea('aviso', `⚠️ ${a}`);
    if (r.pendiente) linea('aviso final', '⏳ Todavía no se puede comprobar: tu voto aún no está sellado.');
    else linea(r.ok ? 'ok final' : 'error final', r.ok ? '✅ Tu voto consta en la urna.' : '❌ La comprobación ha fallado: no des por válido este resultado.');
  } catch (e) {
    linea('error', `❌ ${e.message}`);
  }
}

function leerArchivo() {
  const f = $('archivo').files[0];
  if (!f) return;
  const lector = new FileReader();
  lector.addEventListener('load', () => { $('pegado').value = String(lector.result); });
  lector.readAsText(f);
}

async function mostrarLista() {
  try {
    const lista = await listarConvocatorias();
    const caja = $('lista');
    caja.replaceChildren();
    if (lista.length === 0) {
      caja.textContent = 'No hay convocatorias abiertas ahora mismo.';
      return;
    }
    for (const c of lista) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn';
      b.textContent = c.titulo;
      b.addEventListener('click', () => { $('conv').value = c.id; cargar(); });
      caja.append(b);
    }
  } catch (e) {
    estado(`No se pudo obtener la lista de convocatorias: ${e.message}`, 'error');
  }
}

const params = new URLSearchParams(location.search);
if (params.get('conv')) $('conv').value = params.get('conv');
$('cargar').addEventListener('click', cargar);
$('reintentar').addEventListener('click', reintentar);
$('verificar').addEventListener('click', comprobar);
$('archivo').addEventListener('change', leerArchivo);
$('ver').addEventListener('change', () => { $('credencial').type = $('ver').checked ? 'text' : 'password'; });
if ($('conv').value) cargar(); else mostrarLista();
