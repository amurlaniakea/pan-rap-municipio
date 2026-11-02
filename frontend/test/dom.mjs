// Utilidad de pruebas: carga la UI publicada (HTML servido + bundle) en jsdom con fetch real contra el servidor.
import { JSDOM } from 'jsdom';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { resolveObjectURL } from 'node:buffer';

export async function cargarUI(base, consulta = '') {
  const url = `${base}/ui/${consulta}`;
  const html = await (await fetch(url)).text();
  const dom = new JSDOM(html, { url });
  const nativo = globalThis.fetch;
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, location: dom.window.location,
    FileReader: dom.window.FileReader });
  globalThis.fetch = (u, o) => nativo(new URL(u, url).href, o);
  const $ = (id) => document.getElementById(id);
  const esperar = async (cond, ms = 8000) => {
    const fin = Date.now() + ms;
    while (Date.now() < fin) { if (cond()) return true; await new Promise((r) => setTimeout(r, 25)); }
    return false;
  };
  await import(pathToFileURL(resolve('frontend/ui/voto.bundle.js')).href);
  return { $, esperar, html };
}

/** Lee el contenido del enlace de descarga (blob: de Node o data:). */
export async function leerEnlace(href) {
  if (!href) return null;
  if (href.startsWith('data:')) return decodeURIComponent(href.split(',')[1]);
  return await resolveObjectURL(href).text();
}
