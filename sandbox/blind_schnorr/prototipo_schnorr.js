// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha2.js';
import { bytesToNumberBE } from '@noble/curves/abstract/utils';

const CURVE_ORDER = secp256k1.CURVE.n;

function mod(a, b) {
    const result = a % b;
    return result >= 0n ? result : (b + result);
}

function hashToChallenge(R_point, message) {
    const r_bytes = R_point.toRawBytes(true);
    const m_bytes = new TextEncoder().encode(message);
    const combined = new Uint8Array(r_bytes.length + m_bytes.length);
    combined.set(r_bytes);
    combined.set(m_bytes, r_bytes.length);
    const hash = sha256(combined);
    return mod(bytesToNumberBE(hash), CURVE_ORDER);
}

console.log("🔑 1. Generando claves del Validador...");
const x = secp256k1.utils.randomPrivateKey();
const x_bigint = bytesToNumberBE(x);
const Y = secp256k1.ProjectivePoint.fromPrivateKey(x);
console.log("   Clave pública Y generada.");

console.log("\n✍️  2. Validador: Paso 1 (Generar nonce y R_1)...");
const k1 = secp256k1.utils.randomPrivateKey();
const k1_bigint = bytesToNumberBE(k1);
const R1 = secp256k1.ProjectivePoint.BASE.multiply(k1_bigint);
console.log("   R_1 enviado al cliente.");

console.log("\n🙈 3. Cliente: Cegado del mensaje...");
const a = secp256k1.utils.randomPrivateKey();
const b = secp256k1.utils.randomPrivateKey();
const a_bigint = bytesToNumberBE(a);
const b_bigint = bytesToNumberBE(b);

const aG = secp256k1.ProjectivePoint.BASE.multiply(a_bigint);
const bY = Y.multiply(b_bigint);
const R2 = R1.add(aG).add(bY);
console.log("   R_2 calculado.");

const message = "VOTO_CIFRADO_PROPUESTA_A";
const e2 = hashToChallenge(R2, message);
const e1 = mod(e2 + b_bigint, CURVE_ORDER);
console.log("   Desafío cegado e_1 enviado al validador.");

console.log("\n✍️  4. Validador: Firma del desafío cegado...");
const s1 = mod(k1_bigint + (e1 * x_bigint), CURVE_ORDER);
console.log("   s_1 enviado al cliente.");

console.log("\n🔓 5. Cliente: Descifrado de la firma...");
const s2 = mod(s1 + a_bigint, CURVE_ORDER);
console.log("   Firma final (R_2, s_2) obtenida.");

console.log("\n✅ 6. Verificación de la firma...");
const s2G = secp256k1.ProjectivePoint.BASE.multiply(s2);
const e2Y = Y.multiply(e2);
const expectedPoint = R2.add(e2Y);
const isValid = s2G.equals(expectedPoint);

if (isValid) {
    console.log("🎉 ¡ÉXITO! La firma Blind Schnorr es VÁLIDA y matemáticamente correcta.");
} else {
    console.log("❌ ERROR CRÍTICO: La verificación de la firma falló.");
    process.exit(1);
}
