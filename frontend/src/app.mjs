// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
// Interfaz mínima. Solo textContent (nunca innerHTML) y sin scripts ni estilos en línea (CSP estricta).
import { cargarConvocatoria, flujoVoto, enviarVoto, listarConvocatorias } from './voto_schnorr.mjs';

const $ = (id) => document.getElementById(id);
let conv = null;
let tokenPendiente = null;

function estado(texto, clase = '') {
  const el = $('estado');
  el.textContent = texto;
  el.className = clase;
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
    b.type = 'button';
    b.className = 'btn';
    b.textContent = op;
    b.addEventListener('click', () => votar(op));
    caja.append(b);
  }
  $('panel').hidden = false;
  estado(conv.estado === 'emision' || conv.estado === 'votacion' ? 'Convocatoria abierta' : `Convocatoria no abierta (${conv.estado})`);
}

function bloquear(valor) {
  document.querySelectorAll('.btn').forEach((b) => { b.disabled = valor; });
}

async function votar(opcion) {
  const credencial = $('credencial').value.trim();
  if (!credencial) return estado('Introduce tu credencial', 'error');
  bloquear(true);
  estado('Firmando y enviando el voto…');
  try {
    const r = await flujoVoto(conv.id, credencial, opcion);
    estado(`✅ ${r.mensaje}`, 'ok');
  } catch (e) {
    if (e.token) {
      tokenPendiente = e.token;
      $('reintentar').hidden = false;
      estado(`El token se firmó pero el envío falló: ${e.message}. Pulsa «Reintentar envío».`, 'error');
    } else {
      estado(`❌ ${e.message}`, 'error');
      bloquear(false);
    }
  }
}

async function reintentar() {
  try {
    await enviarVoto(conv.id, tokenPendiente);
    tokenPendiente = null;
    $('reintentar').hidden = true;
    estado('✅ Voto registrado', 'ok');
  } catch (e) {
    estado(`❌ ${e.message}`, 'error');
  }
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
if ($('conv').value) cargar(); else mostrarLista();
