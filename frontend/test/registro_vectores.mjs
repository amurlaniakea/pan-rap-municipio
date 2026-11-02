// Comprueba hojas y caminos Merkle con vectores generados por registro.py. Uso: node registro_vectores.mjs <vectores.json>
import { readFileSync } from 'node:fs';
import { hexABytes, bytesAHex } from '../src/voto_core.mjs';
import { hashHoja, hojaVoto, verificarCamino } from '../src/registro.mjs';

const vectores = JSON.parse(readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify(vectores.map((v) => ({
  hoja: bytesAHex(hashHoja(hojaVoto(v.r, v.s, v.opcion))),
  camino_ok: verificarCamino(hashHoja(hojaVoto(v.r, v.s, v.opcion)), v.i, v.n, v.camino.map(hexABytes), hexABytes(v.raiz)),
}))));
