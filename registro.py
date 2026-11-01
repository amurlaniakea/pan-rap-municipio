# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Registro verificable de la urna durante la votación (Fase 7).

Los votos aceptados se sellan por lotes en *checkpoints* firmados y encadenados:
  checkpoint k = firma_log( "PANRAP-CKPT-v1|conv|k|n|raíz|hash(k-1)|fecha" )
donde `raíz` es la raíz Merkle (RFC 6962) de las hojas de los n primeros votos sellados, ordenados por
(lote, r'). Dentro de un lote el orden es el de r' (no el de llegada): solo se revela el orden entre lotes.
Los checkpoints no revelan opciones ni tokens; al cierre la urna publica los votos con su lote y cualquiera
puede recalcular todas las raíces.

Garantías (con observadores que archiven los checkpoints durante la votación): detectar votos reales
retirados o modificados tras sellarse y detectar que el servidor muestre historias distintas a observadores
distintos (la firma convierte la contradicción en prueba transferible).
NO impide que el operador fabrique votos con su clave de firma ni protege los votos aún sin sellar."""
import hashlib

from coincurve import PrivateKey, PublicKey

from urna_publica import hoja_voto

GENESIS = "00" * 32


def _sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


# ---------- árbol de Merkle (RFC 6962) ----------

def hash_hoja(datos: bytes) -> bytes:
    return _sha(b"\x00" + datos)


def _nodo(izq: bytes, der: bytes) -> bytes:
    return _sha(b"\x01" + izq + der)


def _mayor_potencia_menor(n: int) -> int:
    return 1 << ((n - 1).bit_length() - 1)


def raiz(hojas: list) -> bytes:
    """Raíz del árbol sobre una lista de hashes de hoja."""
    n = len(hojas)
    if n == 0:
        return _sha(b"")
    if n == 1:
        return hojas[0]
    k = _mayor_potencia_menor(n)
    return _nodo(raiz(hojas[:k]), raiz(hojas[k:]))


def camino(hojas: list, i: int) -> list:
    """Camino de inclusión de la hoja i (el hermano más exterior va el último)."""
    n = len(hojas)
    if not 0 <= i < n:
        raise IndexError(i)
    if n == 1:
        return []
    k = _mayor_potencia_menor(n)
    if i < k:
        return camino(hojas[:k], i) + [raiz(hojas[k:])]
    return camino(hojas[k:], i - k) + [raiz(hojas[:k])]


def verificar_camino(hoja: bytes, i: int, n: int, ruta: list, raiz_esperada: bytes) -> bool:
    def calc(i, n, ruta):
        if n == 1:
            return hoja if not ruta else None
        if not ruta:
            return None
        k = _mayor_potencia_menor(n)
        resto, ultimo = ruta[:-1], ruta[-1]
        if i < k:
            sub = calc(i, k, resto)
            return None if sub is None else _nodo(sub, ultimo)
        sub = calc(i - k, n - k, resto)
        return None if sub is None else _nodo(ultimo, sub)

    if not 0 <= i < n:
        return False
    return calc(i, n, list(ruta)) == raiz_esperada


def hojas_de_votos(votos) -> list:
    """votos: iterable de (r_prima, s_prima, opcion) YA en el orden del registro (lote, r')."""
    return [hash_hoja(hoja_voto(r, s, op)) for r, s, op in votos]


# ---------- checkpoints ----------

def mensaje_checkpoint(conv_id: str, cp: dict) -> bytes:
    return f"PANRAP-CKPT-v1|{conv_id}|{cp['seq']}|{cp['n']}|{cp['root']}|{cp['prev']}|{cp['creado']}".encode()


def hash_checkpoint(conv_id: str, cp: dict) -> str:
    return _sha(mensaje_checkpoint(conv_id, cp) + bytes.fromhex(cp["firma"])).hex()


def firmar_checkpoint(d_log: bytes, conv_id: str, cp: dict) -> str:
    """Devuelve la firma ECDSA (DER, hex) del checkpoint (cp sin 'firma')."""
    return PrivateKey(d_log).sign(mensaje_checkpoint(conv_id, cp)).hex()


def _firma_valida(pub: bytes, conv_id: str, cp: dict) -> bool:
    try:
        return PublicKey(pub).verify(bytes.fromhex(cp["firma"]), mensaje_checkpoint(conv_id, cp))
    except Exception:  # firma mal formada, clave inválida, campos ausentes…: nunca válida
        return False


def verificar_cadena(conv_id: str, log_pub: bytes, checkpoints: list) -> list:
    """Firmas, encadenamiento, numeración consecutiva y n no decreciente. Devuelve la lista de problemas."""
    problemas, anterior = [], None
    for i, cp in enumerate(checkpoints, 1):
        try:
            if cp["seq"] != i:
                problemas.append(f"checkpoint {i}: numeración no consecutiva (seq={cp['seq']})")
            if not _firma_valida(log_pub, conv_id, cp):
                problemas.append(f"checkpoint {i}: firma inválida")
            esperado = GENESIS if anterior is None else hash_checkpoint(conv_id, anterior)
            if cp["prev"] != esperado:
                problemas.append(f"checkpoint {i}: no encadena con el anterior")
            if anterior is not None and cp["n"] < anterior["n"]:
                problemas.append(f"checkpoint {i}: n decrece ({anterior['n']} → {cp['n']})")
        except (KeyError, TypeError, ValueError):
            problemas.append(f"checkpoint {i}: formato inválido")
        anterior = cp
    return problemas


def verificar_votos(checkpoints: list, votos: list) -> list:
    """votos: [(r_prima, s_prima, opcion, lote)]. Recalcula cada raíz sobre los votos sellados hasta ese lote."""
    problemas = []
    if any(v[3] is None for v in votos):
        problemas.append("hay votos sin sellar en ningún checkpoint")
    ordenados = sorted((v for v in votos if v[3] is not None), key=lambda v: (v[3], bytes(v[0])))
    hojas = hojas_de_votos([(r, s, op) for r, s, op, _ in ordenados])
    for cp in checkpoints:
        try:
            n_lote = sum(1 for v in ordenados if v[3] <= cp["seq"])
            if n_lote != cp["n"]:
                problemas.append(f"checkpoint {cp['seq']}: declara n={cp['n']} y la urna tiene {n_lote} votos hasta ese lote")
            elif raiz(hojas[:n_lote]).hex() != cp["root"]:
                problemas.append(f"checkpoint {cp['seq']}: la raíz no coincide con los votos publicados")
        except (KeyError, TypeError, ValueError):
            problemas.append("checkpoint con formato inválido")
    ultimo = checkpoints[-1]["seq"] if checkpoints else 0
    if any(v[3] is not None and v[3] > ultimo for v in votos):
        problemas.append("hay votos asignados a lotes posteriores al último checkpoint")
    if checkpoints and checkpoints[-1]["n"] != len(votos):
        problemas.append(f"el último checkpoint declara n={checkpoints[-1]['n']} y la urna tiene {len(votos)} votos")
    if not checkpoints:
        problemas.append("no hay ningún checkpoint")
    return problemas


def comparar_con_archivo(archivados: list, servidos: list) -> list:
    """Compara lo que un observador archivó con lo que sirve ahora el servidor (misma seq ⇒ idéntico)."""
    problemas = []
    if len(servidos) < len(archivados):
        problemas.append(f"RETROCESO: el servidor sirve {len(servidos)} checkpoints y había archivados {len(archivados)}")
    por_seq = {cp.get("seq"): cp for cp in servidos}
    for cp in archivados:
        actual = por_seq.get(cp.get("seq"))
        if actual is not None and actual != cp:
            problemas.append(f"EQUIVOCACIÓN en el checkpoint {cp.get('seq')}: el servidor firmó dos contenidos distintos")
    return problemas


def verificar_registro(conv_id: str, log_pub: bytes, checkpoints: list, votos: list) -> list:
    return verificar_cadena(conv_id, log_pub, checkpoints) + verificar_votos(checkpoints, votos)
