(() => {
  // frontend/voto_schnorr.js
  function bytesToHex(b) {
    return Array.from(b).map((x) => x.toString(16).padStart(2, "0")).join("");
  }
  function hexToBytes(h) {
    return new Uint8Array(h.match(/.{1,2}/g).map((x) => parseInt(x, 16)));
  }
  function bigIntToBytes32(num) {
    const hex = num.toString(16).padStart(64, "0");
    return hexToBytes(hex);
  }
  function bytesToBigInt(b) {
    const hex = bytesToHex(b);
    return BigInt("0x" + hex);
  }
  async function flujoVoto(opcion, endpointInicio, endpointFin, endpointVoto) {
    const respInicio = await fetch(endpointInicio, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ convocatoria_id: "test" }) });
    const dataInicio = await respInicio.json();
    if (!respInicio.ok)
      throw new Error("Inicio fallido: " + (dataInicio.detail || respInicio.statusText));
    const R_hex = dataInicio.R;
    const R_bytes = hexToBytes(R_hex);
    const a_bytes = new Uint8Array(32);
    const b_bytes = new Uint8Array(32);
    crypto.getRandomValues(a_bytes);
    crypto.getRandomValues(b_bytes);
    const a = bytesToBigInt(a_bytes);
    const b = bytesToBigInt(b_bytes);
    const m_str = "PANRAP-v1|test|" + opcion;
    const m_bytes = new TextEncoder().encode(m_str);
    const e_bytes = new Uint8Array(32);
    crypto.getRandomValues(e_bytes);
    e_bytes[0] = 1;
    const e_hex = bytesToHex(e_bytes);
    const respFin = await fetch(endpointFin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sesion: dataInicio.sid, e: e_hex })
    });
    const dataFin = await respFin.json();
    if (!respFin.ok)
      throw new Error("Fin fallido: " + (dataFin.detail || respFin.statusText));
    const s_bytes = hexToBytes(dataFin.s);
    const s_big = bytesToBigInt(s_bytes);
    const s_prima_big = (s_big + a) % BigInt("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141");
    const s_prima_hex = bytesToHex(bigIntToBytes32(s_prima_big));
    const respVoto = await fetch(endpointVoto, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ opcion, r_prima: bytesToHex(new Uint8Array(R_bytes)), s_prima: s_prima_hex })
    });
    const dataVoto = await respVoto.json();
    if (!respVoto.ok)
      throw new Error("Voto rechazado: " + (dataVoto.detail || respVoto.statusText));
    return { mensaje: "Voto registrado an\xF3nimamente", id: dataVoto.id };
  }
  if (typeof window !== "undefined") {
    window.flujoVoto = flujoVoto;
    window.bytesToHex = bytesToHex;
    window.hexToBytes = hexToBytes;
  }
})();
