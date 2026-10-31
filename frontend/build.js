const esbuild = require('esbuild');

esbuild.build({
  entryPoints: ['frontend/voto_schnorr.js'],
  bundle: true,
  minify: true,
  outfile: 'frontend/voto.bundle.js',
  format: 'esm',
  target: ['es2020'],
  alias: {
    '@noble/curves/secp256k1': './frontend/lib/noble/curves/secp256k1.js',
    '@noble/curves/secp256k1.js': './frontend/lib/noble/curves/secp256k1.js',
    '@noble/curves': './frontend/lib/noble/curves/index.js',
    '@noble/hashes/sha2.js': './frontend/lib/noble/hashes/sha2.js',
    '@noble/hashes/sha2': './frontend/lib/noble/hashes/sha2.js',
    '@noble/hashes/utils': './frontend/lib/noble/hashes/utils.js',
    '@noble/hashes/utils.js': './frontend/lib/noble/hashes/utils.js',
    '@noble/hashes/hmac.js': './frontend/lib/noble/hashes/hmac.js',
    '@noble/hashes': './frontend/lib/noble/hashes/index.js',
  },
  mainFields: ['module', 'main'],
  resolveExtensions: ['.js', '.mjs'],
}).catch(() => process.exit(1));