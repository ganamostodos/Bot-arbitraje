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

BITUNIX_URL = "https://fapi.bitunix.com/api/v1/futures/market/tickers"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"

# Para no repetir la misma alerta cada minuto mientras el spread siga
# abierto, guardamos si ya se notificó para cada símbolo y solo
# volvemos a avisar si el spread se cerró y volvió a abrirse.
_alertas_activas = {symbol: False for symbol in SYMBOLS}


def obtener_precios_bitunix(symbols):
    """Devuelve un diccionario {symbol: precio} usando lastPrice de Bitunix."""
    try:
        params = {"symbols": ",".join(symbols)}
        response = requests.get(BITUNIX_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        precios = {}
        for item in data.get("data", []):
            precios[item["symbol"]] = float(item["lastPrice"])
        return precios
    except Exception as e:
        log.error(f"Error consultando precios en Bitunix: {e}")
        return {}


def obtener_precio_binance(symbol):
    """Devuelve el precio actual de un símbolo en Binance."""
    try:
        response = requests.get(BINANCE_URL, params={"symbol": symbol}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return float(data["price"])
    except Exception as e:
        log.error(f"Error consultando precio de {symbol} en Binance: {e}")
        return None


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
    precios_bitunix = obtener_precios_bitunix(SYMBOLS)

    for symbol in SYMBOLS:
        precio_bitunix = precios_bitunix.get(symbol)
        precio_binance = obtener_precio_binance(symbol)

        if precio_bitunix is None or precio_binance is None:
            log.warning(f"{symbol}: no se pudo obtener precio de ambos exchanges, se omite.")
            continue

        diferencia = precio_bitunix - precio_binance
        spread_pct = (diferencia / precio_binance) * 100

        log.info(
            f"{symbol} | Bitunix: {precio_bitunix} | Binance: {precio_binance} "
            f"| Spread: {spread_pct:.3f}%"
        )

        if abs(spread_pct) >= SPREAD_THRESHOLD:
            if not _alertas_activas[symbol]:
                mas_barato = "Binance" if diferencia > 0 else "Bitunix"
                mas_caro = "Bitunix" if diferencia > 0 else "Binance"
                mensaje = (
                    f"🚨 <b>Oportunidad de arbitraje: {symbol}</b>\n\n"
                    f"Bitunix: {precio_bitunix}\n"
                    f"Binance: {precio_binance}\n"
                    f"Spread: <b>{abs(spread_pct):.3f}%</b>\n\n"
                    f"Más barato en {mas_barato}, más caro en {mas_caro}."
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
