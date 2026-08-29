# Bot de Notificaciones de Arbitraje - Bitunix vs Binance

Compara el **bid/ask real** (no el último precio negociado) de varios pares
entre Bitunix y Binance cada minuto, y envía una alerta a Telegram cuando
hay una oportunidad de arbitraje ejecutable. **No ejecuta ninguna
operación**, solo notifica.

## Cómo funciona la comparación

Una oportunidad de arbitraje real se basa en el precio al que realmente
puedes comprar (ask) y vender (bid) — no en el último precio negociado. El
bot evalúa las dos direcciones posibles:

- **Comprar en Binance (ask) y vender en Bitunix (bid)**
- **Comprar en Bitunix (ask) y vender en Binance (bid)**

y te avisa con la dirección que dé mejor spread, si supera el umbral
configurado.

## Archivos

- `bot.py` — script principal
- `requirements.txt` — dependencias (solo `requests`)

## Paso 1 — Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envíale `/newbot`
3. Elige un nombre para mostrar (ej. "Alertas Arbitraje") y un username que
   termine en "bot" (ej. `ganamostodos_arbitraje_bot`)
4. BotFather te da un **token** (ej. `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`) — guárdalo

## Paso 2 — Obtener tu chat_id

1. Envíale cualquier mensaje a tu bot recién creado (búscalo y dale "Iniciar")
   — o agrégalo al grupo donde quieres recibir las alertas
2. Visita en el navegador (reemplazando `<TU_TOKEN>`):
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
3. Busca `"chat":{"id": ...}` — ese número es tu `chat_id`
   (para grupos, el número suele empezar con `-`)

## Paso 3 — Despliegue en Railway

1. Crea un nuevo repositorio en GitHub y sube `bot.py` y `requirements.txt`
2. En Railway: "New Project" → "Deploy from GitHub repo" → selecciona el repositorio
3. En la pestaña **Variables**, agrega:
   - `TELEGRAM_BOT_TOKEN` → el token de BotFather
   - `TELEGRAM_CHAT_ID` → el chat_id que obtuviste
   - `SYMBOLS` → (opcional) `ADAUSDT,AVAXUSDT,TONUSDT` (ya es el valor por defecto)
   - `SPREAD_THRESHOLD` → (opcional) `0.5` (avisa si la diferencia es de 0.5% o más;
     ajústalo si quieres alertas más o menos frecuentes)
   - `CHECK_INTERVAL` → (opcional) `60` (segundos entre cada revisión)
4. En **Settings → Deploy**, confirma que el "Start Command" sea:
   ```
   python bot.py
   ```
5. Dale deploy

## Notas

- Ambas consultas de precio son **públicas**, no requieren cuenta ni API key
  de Bitunix ni de Binance
- El bot evita mandarte la misma alerta repetidamente mientras el spread siga
  abierto — solo vuelve a avisar si el spread se cerró y se volvió a abrir
- Puedes agregar o quitar pares editando la variable `SYMBOLS` en Railway,
  sin tocar el código
  
