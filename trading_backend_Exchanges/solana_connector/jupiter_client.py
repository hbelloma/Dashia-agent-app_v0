"""
jupiter_client.py
==================
Cliente del Jupiter Swap API — v2 (actual) con v1 como respaldo gratis.

Verificado contra la documentación OFICIAL vigente en septiembre 2026
(developers.jup.ag/docs/swap, fetcheada directo, no un resumen de
terceros): Jupiter unificó su API en `https://api.jup.ag/swap/v2`, con
dos caminos:

  - Meta-Aggregator (/order + /execute): el recomendado. Todos los
    motores de ruteo compiten (Metis on-chain + JupiterZ/RFQ + Dflow +
    OKX), mejor precio, y Jupiter gestiona el "landing" de la
    transacción (reintentos, fees de prioridad optimizados) — esto es
    justo lo que pedía la idea original de "trades rápidos".
  - Router (/build + /submit): para quien necesita armar su propia
    transacción (CPI, instrucciones custom) — no se implementa acá, no
    hace falta para este proyecto.

DIFERENCIA IMPORTANTE con v1: v2 exige API key SIEMPRE
("All endpoints require an API key via the x-api-key header") — no
existe un `lite-api.jup.ag/swap/v2` gratis equivalente al que sí existe
para v1. Por eso este cliente NO reemplaza v1, lo complementa: si hay
JUPITER_API_KEY configurada, usa v2 (mejor precio, landing gestionado);
si no, cae a v1 (gratis, vos mandás la transacción por tu propio RPC).

Nivel de confianza, honesto: el flujo de endpoints, headers y el
patrón order->sign->execute están confirmados contra la documentación
oficial. Los nombres exactos de un par de campos opcionales del cuerpo
de /order (más allá de inputMint/outputMint/amount/taker/slippageBps)
se infirieron de las convenciones que Jupiter usa en el resto de su
API (Ultra API tiene una estructura casi idéntica) — vale la pena
confirmarlos contra una respuesta real antes de producción, algo que
este sandbox no pudo hacer por no tener salida de red hacia jup.ag.
"""

from __future__ import annotations
import logging
import requests

from .config import SolanaSettings, WELL_KNOWN_MINTS

log = logging.getLogger("jupiter_client")


class JupiterAPIError(RuntimeError):
    pass


class JupiterClient:
    def __init__(self, settings: SolanaSettings, timeout: float = 12.0):
        self.settings = settings
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"x-api-key": self.settings.jupiter_api_key} if self.settings.jupiter_api_key else {}

    # ==================================================================
    # v2 — RECOMENDADO (requiere JUPITER_API_KEY)
    # ==================================================================
    def get_order(self, input_mint: str, output_mint: str, amount: int, taker_pubkey: str,
                   slippage_bps: int | None = None) -> dict:
        """
        GET /swap/v2/order — reemplaza en un solo call lo que en v1 eran
        dos (get_quote + get_swap_transaction). Devuelve la cotización Y
        la transacción ya ensamblada, lista para firmar.

        `transaction` viene en base64; null si no se pudo armar (revisar
        errorCode en la respuesta) — no asumir que siempre viene.
        """
        if not self.settings.jupiter_api_key:
            raise JupiterAPIError(
                "get_order() es v2 y requiere JUPITER_API_KEY (gratis, con cupo mensual, "
                "en https://developers.jup.ag/portal). Sin key, usar get_quote()+get_swap_transaction() (v1)."
            )
        params = {
            "inputMint": input_mint, "outputMint": output_mint, "amount": amount,
            "taker": taker_pubkey, "slippageBps": slippage_bps or self.settings.default_slippage_bps,
        }
        resp = requests.get(f"{self.settings.jupiter_v2_base_url}/order",
                             params=params, headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise JupiterAPIError(f"/order falló ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        if not data.get("transaction"):
            raise JupiterAPIError(
                f"/order no devolvió una transacción armada (errorCode={data.get('errorCode')}): {data}"
            )
        return data

    def execute_order(self, signed_transaction_b64: str, request_id: str) -> dict:
        """
        POST /swap/v2/execute — se le manda la transacción YA FIRMADA
        (por la wallet operativa, ver wallet.py) y Jupiter se encarga de
        mandarla a la red con su pipeline de landing optimizado
        (reintentos, fees de prioridad dinámicos). A diferencia de v1,
        acá NO hace falta llamar a SolanaRPC.send_raw_transaction —
        Jupiter hace ese paso por vos.

        `request_id` es el que devuelve get_order() — enlaza la
        ejecución con la cotización original.
        """
        if not self.settings.jupiter_api_key:
            raise JupiterAPIError("execute_order() es v2 y requiere JUPITER_API_KEY.")
        body = {"signedTransaction": signed_transaction_b64, "requestId": request_id}
        resp = requests.post(f"{self.settings.jupiter_v2_base_url}/execute",
                              json=body, headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise JupiterAPIError(f"/execute falló ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        if data.get("status") == "Failed":
            raise JupiterAPIError(f"Jupiter no pudo landear la transacción: {data}")
        return data

    # ==================================================================
    # v1 — LEGACY, respaldo gratis (lite-api.jup.ag, sin API key)
    # ==================================================================
    def get_quote(self, input_mint: str, output_mint: str, amount: int,
                  slippage_bps: int | None = None) -> dict:
        """
        amount: monto de entrada en unidades atómicas (lamports para SOL,
        o la unidad mínima del token según sus decimales — no en "SOL
        completos").
        """
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage_bps or self.settings.default_slippage_bps,
            "restrictIntermediateTokens": "true",
        }
        resp = requests.get(f"{self.settings.jupiter_base_url}/quote",
                             params=params, headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise JupiterAPIError(f"quote falló ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    def get_swap_transaction(self, quote_response: dict, user_pubkey: str,
                              priority_fee_lamports: int | None = "auto") -> str:
        """Devuelve el `swapTransaction` en base64, listo para firmar.
        A diferencia de v2, acá SÍ hace falta mandar la tx vos mismo por
        RPC después (ver SolanaRPC.send_raw_transaction en rpc.py)."""
        body = {
            "quoteResponse": quote_response,
            "userPublicKey": user_pubkey,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": priority_fee_lamports,
        }
        resp = requests.post(f"{self.settings.jupiter_base_url}/swap",
                              json=body, headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise JupiterAPIError(f"swap falló ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        if "swapTransaction" not in data:
            raise JupiterAPIError(f"Respuesta de /swap sin swapTransaction: {data}")
        return data["swapTransaction"]

    # ------------------------------------------------------------------
    def resolve_mint_by_symbol(self, symbol: str) -> str:
        """
        Busca el mint address real de un símbolo. Solo SOL/USDC/USDT están
        hardcodeados (verificados); todo lo demás se resuelve en vivo
        contra la Token API de Jupiter para no arriesgar una dirección
        adivinada — un mint incorrecto en Solana no falla con un error
        claro, puede simplemente operar el token equivocado.
        """
        symbol = symbol.upper()
        if symbol in WELL_KNOWN_MINTS:
            return WELL_KNOWN_MINTS[symbol]
        if not self.settings.jupiter_api_key:
            raise JupiterAPIError(
                f"'{symbol}' no está en la lista verificada local. Resolverlo en vivo "
                f"requiere JUPITER_API_KEY (gratis en https://developers.jup.ag/portal) para usar "
                f"la Token API de Jupiter."
            )
        resp = requests.get("https://api.jup.ag/tokens/v2/search", params={"query": symbol},
                             headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise JupiterAPIError(f"token search falló ({resp.status_code}): {resp.text[:300]}")
        results = resp.json()
        exact = [t for t in results if t.get("symbol", "").upper() == symbol and t.get("isVerified")]
        if not exact:
            raise JupiterAPIError(f"No se encontró un token verificado con símbolo '{symbol}'")
        return exact[0]["id"]
