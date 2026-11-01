// Construye frontend/ui/voto.bundle.js desde frontend/src con las dependencias fijadas en package-lock.json
// (@noble/curves, @noble/hashes: MIT; sus avisos de licencia se conservan al final del bundle) y publica su SHA-256.
// Reproducible: `npm ci && node frontend/build.js` debe dejar el árbol sin cambios (se comprueba en CI).
const esbuild = require('esbuild');
const crypto = require('crypto');
const fs = require('fs');

esbuild.build({
  entryPoints: ['frontend/src/app.mjs'],
  bundle: true,
  minify: true,
  outfile: 'frontend/ui/voto.bundle.js',
  format: 'esm',
  target: ['es2020'],
  legalComments: 'eof',
  logLevel: 'warning',
}).then(() => {
  const hash = crypto.createHash('sha256').update(fs.readFileSync('frontend/ui/voto.bundle.js')).digest('hex');
  fs.writeFileSync('frontend/SHA256SUMS', `${hash}  ui/voto.bundle.js\n`);
  console.log(`voto.bundle.js sha256=${hash}`);
}).catch(() => process.exit(1));
