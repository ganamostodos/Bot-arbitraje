"""
Bot de Notificaciones de Arbitraje - Bitunix vs Binance
Compara el precio de varios pares entre Bitunix y Binance cada cierto
intervalo, y envía una alerta a Telegram cuando la diferencia porcentual
(spread) supera un umbral definido. No ejecuta ninguna operación,
solo notifica.

Variables de entorno necesarias (configúralas en Railway):
    TELEGRAM_BOT_TOKEN   -> Token del bot, dado por @BotFather
    TELEGRAM_CHAT_ID     -> ID del chat/grupo al que se envían las alertas
    SYMBOLS              -> Pares a monitorear, separados por coma (opcional,
                             default: ADAUSDT,AVAXUSDT,TONUSDT)
    SPREAD_THRESHOLD     -> % mínimo de diferencia para notificar (opcional,
                             default: 0.5)
    CHECK_INTERVAL       -> segundos entre cada revisión (opcional, default: 60)
"""

import os
import time
import logging

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bot_arbitraje")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SYMBOLS = [s.strip() for s in os.environ.get("SYMBOLS", "ADAUSDT,AVAXUSDT,TONUSDT").split(",")]
SPREAD_THRESHOLD = float(os.environ.get("SPREAD_THRESHOLD", "0.5"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))

BITUNIX_DEPTH_URL = "https://fapi.bitunix.com/api/v1/futures/market/depth"
# Endpoint de solo datos públicos de mercado, sin restricción geográfica
BINANCE_BOOKTICKER_URL = "https://data-api.binance.vision/api/v3/ticker/bookTicker"

# Para no repetir la misma alerta cada minuto mientras el spread siga
# abierto, guardamos si ya se notificó para cada símbolo y solo
# volvemos a avisar si el spread se cerró y volvió a abrirse.
_alertas_activas = {symbol: False for symbol in SYMBOLS}


def obtener_bid_ask_bitunix(symbol):
    """Devuelve (bid, ask) del mejor precio disponible en el order book de
    Bitunix para el símbolo dado, o (None, None) si falla."""
    try:
        response = requests.get(
            BITUNIX_DEPTH_URL, params={"symbol": symbol, "limit": "1"}, timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") not in (0, None):
            log.warning(f"Bitunix: {symbol} no disponible ({data.get('msg', data)}).")
            return None, None

        book = data.get("data") or {}
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        if not bids or not asks:
            return None, None

        mejor_bid = float(bids[0][0])
        mejor_ask = float(asks[0][0])
        return mejor_bid, mejor_ask
    except Exception as e:
        log.error(f"Error consultando order book de {symbol} en Bitunix: {e}")
        return None, None


def obtener_bid_ask_binance(symbol):
    """Devuelve (bid, ask) del mejor precio disponible en Binance para el
    símbolo dado, o (None, None) si falla."""
    try:
        response = requests.get(
            BINANCE_BOOKTICKER_URL, params={"symbol": symbol}, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        return float(data["bidPrice"]), float(data["askPrice"])
    except Exception as e:
        log.error(f"Error consultando order book de {symbol} en Binance: {e}")
        return None, None


def enviar_telegram(mensaje: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Faltan las variables TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Error enviando mensaje a Telegram: {e}")
        return False


def revisar_spreads():
    for symbol in SYMBOLS:
        bid_bitunix, ask_bitunix = obtener_bid_ask_bitunix(symbol)
        bid_binance, ask_binance = obtener_bid_ask_binance(symbol)

        if None in (bid_bitunix, ask_bitunix, bid_binance, ask_binance):
            log.warning(f"{symbol}: no se pudo obtener bid/ask de ambos exchanges, se omite.")
            continue

        # Dirección 1: comprar en Binance (ask) y vender en Bitunix (bid)
        spread_1_pct = ((bid_bitunix - ask_binance) / ask_binance) * 100
        # Dirección 2: comprar en Bitunix (ask) y vender en Binance (bid)
        spread_2_pct = ((bid_binance - ask_bitunix) / ask_bitunix) * 100

        mejor_spread = max(spread_1_pct, spread_2_pct)
        direccion = 1 if spread_1_pct >= spread_2_pct else 2

        log.info(
            f"{symbol} | Binance bid/ask: {bid_binance}/{ask_binance} "
            f"| Bitunix bid/ask: {bid_bitunix}/{ask_bitunix} "
            f"| Mejor spread: {mejor_spread:.3f}% (dirección {direccion})"
        )

        if mejor_spread >= SPREAD_THRESHOLD:
            if not _alertas_activas[symbol]:
                if direccion == 1:
                    mensaje = (
                        f"🚨 <b>Oportunidad de arbitraje: {symbol}</b>\n\n"
                        f"Comprar en Binance a {ask_binance}\n"
                        f"Vender en Bitunix a {bid_bitunix}\n"
                        f"Spread: <b>{spread_1_pct:.3f}%</b>"
                    )
                else:
                    mensaje = (
                        f"🚨 <b>Oportunidad de arbitraje: {symbol}</b>\n\n"
                        f"Comprar en Bitunix a {ask_bitunix}\n"
                        f"Vender en Binance a {bid_binance}\n"
                        f"Spread: <b>{spread_2_pct:.3f}%</b>"
                    )
                if enviar_telegram(mensaje):
                    log.info(f"Alerta enviada para {symbol}.")
                    _alertas_activas[symbol] = True
        else:
            # El spread volvió a niveles normales; permite notificar de nuevo
            # la próxima vez que se abra.
            _alertas_activas[symbol] = False


def ciclo_principal():
    log.info("Bot de arbitraje iniciado.")
    log.info(f"Monitoreando: {', '.join(SYMBOLS)}")
    log.info(f"Umbral de spread: {SPREAD_THRESHOLD}% | Intervalo: {CHECK_INTERVAL}s")

    while True:
        try:
            revisar_spreads()
        except Exception as e:
            log.error(f"Error inesperado en el ciclo: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    ciclo_principal()
