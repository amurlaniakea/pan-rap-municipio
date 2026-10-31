# SPDX-License-Identifier: AGPL-3.0-or-later
# Contrato rojo T0 — debe fallar con AssertionError hasta que helpers_api.py y conftest.py estén listos
import pytest
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

@pytest.mark.xfail(strict=True, raises=(AssertionError, ImportError, AttributeError, TypeError), reason="T0: helpers_api.blindar debe funcionar con el Emisor actualizado")
def test_blindar_ref_interoperabilidad():
    # Este test usa helpers_api.py que aún no existe; debe fallar con ImportError/AssertionError.
    from tests import helpers_api
    from coincurve import PrivateKey
    import urna_schnorr as U
    from emisor_schnorr import Emisor
    Y = Emisor(PrivateKey()).Y
    R_prima, s_prima = helpers_api.emitir_token(None, "conv", "cred", "opcion", Y)
    # Si llega aquí, el contrato está cumplido; mientras tanto xfail.
    assert False, "T0: este test debe pasar después de helpers_api.py"
