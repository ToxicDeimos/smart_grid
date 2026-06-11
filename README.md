# smart_grid

Detector de **suelos de ciclo** de Bitcoin + herramientas de **acumulación spot** y grids, para Pionex.

> **⚠️ Hallazgo clave de la investigación** ([docs/RESEARCH.md](docs/RESEARCH.md)): tras un
> backtesting exhaustivo con validación out-of-sample, **ningún grid bate a comprar y mantener
> BTC** — el edge de BTC es su drift alcista y el grid lo destruye (el apalancado por la cola, el
> spot por vender pronto). Lo que **sí** funciona es el **DCA inteligente**: acumular spot
> ponderando por el score de suelo de ciclo (ROI +71.5% vs +50.4% del DCA plano). Prueba
> `python scripts/run_dca.py --base 100`.

El sistema responde a dos preguntas:

1. **¿Estamos en zona de suelo de ciclo?** — un termómetro 0–100 que combina señales de
   precio y on-chain en un score de confluencia.
2. **¿Qué bot de grid montar y con qué parámetros?** — tipo de bot (Long / Short / Neutral),
   zona de entrada / trigger, rango (límites inferior/superior), nº de grids, apalancamiento,
   Stop Loss y Take Profit. (La liquidación la calcula Pionex al crear el bot.)

Es un **recomendador**: calcula y muestra los parámetros; tú los introduces en Pionex a mano.
No ejecuta órdenes (la API de futuros de Pionex es *invite-only*).

---

## ⚠️ Aviso importante

- **Esto NO es asesoramiento financiero.** Los grids de futuros usan apalancamiento y pueden
  **liquidar tu capital** si el precio sale del rango. Arriesga solo lo que puedas perder.
- **Sobre el edge:** los suelos de ciclo son de lo poco en BTC con valor predictivo histórico,
  porque son eventos de **valoración extrema** (capitulación), no de *timing* fino. Pero hay
  una limitación fundamental: **N ≈ 3-4 ciclos** (2011, 2015, 2018, 2022). Con tan pocas
  muestras **no existe validación estadística out-of-sample posible**, y los ETFs (2024) pueden
  haber alterado el comportamiento de ciclo. Trata este sistema como un **marco de gestión de
  riesgo por valoración extrema**, para *dimensionar y escalonar* entradas — **no** como un
  gatillo mecánico con edge demostrado.

---

## Señales del detector de suelos

**Precio** (vía ccxt / Binance spot, gratis):
- Posición frente a la **media de 200 semanas (200WMA)**
- **Mayer Multiple** (precio ÷ 200DMA)
- **Drawdown** desde el ATH
- **RSI mensual**
- **Bull Market Support Band** (20W SMA + 21W EMA)

**On-chain** (gratis y sin key):
- **MVRV Z-Score** (bitcoin-data.com) ✅
- **Realized Price** — precio < realized = capitulación (bitcoin-data.com) ✅
- **Hash Ribbons** — capitulación de mineros + recuperación (blockchain.info) ✅
- **Puell Multiple** — ingresos de mineros (blockchain.info) ✅

Si una fuente falla, su señal se omite del score, que **renormaliza** los pesos del resto.

**Altcoins (no BTC):** el score usa las señales de precio del propio activo **más** una
señal requerida **"Suelo de Bitcoin"** (peso alto). Una altcoin no hace suelo de ciclo si
BTC no lo ha hecho, así que actúa de _gate_; las métricas on-chain (de la red Bitcoin) se
consolidan en ella.

---

## Instalación

```bash
python -m venv venv
# Windows (CMD / PowerShell):
venv\Scripts\activate
# Windows (Git Bash):
source venv/Scripts/activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

No hace falta ninguna clave API en v1: todas las fuentes de datos son públicas/gratuitas.

## Uso

```bash
# Termómetro de suelo actual (cada señal + score 0-100, incluye la 200WMA de hoy)
python scripts/bottom_dashboard.py

# DCA inteligente: cuanto comprar BTC spot hoy segun el score (lo que SI tiene edge)
python scripts/run_dca.py --base 100

# Recomendación completa de bot de grid para un capital dado
python scripts/run_recommendation.py --capital 2000 --symbol BTC/USDT

# Sanity-check de las señales contra los suelos historicos (2018, 2022)
python scripts/backtest_signals.py
```

### Panel web

```bash
python web/app.py     # luego abre http://127.0.0.1:5000
```

Panel interactivo (Flask): termómetro de suelo, las señales, recomendación de bot
(rango, grids, apalancamiento, SL/TP, avisos) y un gráfico del precio con los
niveles del grid marcados. Inputs de capital y símbolo.

## Estructura

```
src/
  data/        # ccxt (mercado) + bitcoin-data.com / blockchain.info (on-chain) + cache
  signals/     # señales de precio, on-chain, Suelo de Bitcoin y score de confluencia
  regime/      # tendencia vs rango
  grid/        # tipo de bot + optimizador de parametros (rango, grids, SL/TP)
  report.py    # ensambla la recomendacion
scripts/       # CLIs: bottom_dashboard, run_recommendation, backtest_signals
config/        # config.yaml (umbrales, pesos, fees)
tests/         # pytest
```

## Configuración

Todos los umbrales de señales, pesos del score, fees y restricciones de Pionex
(apalancamiento mínimo 3x) están en [`config/config.yaml`](config/config.yaml).

## Estado

**v1 funcional** con las 9 señales activas (5 de precio + 4 on-chain, todas gratis y sin
key) más la señal **Suelo de Bitcoin** para altcoins. Detector de suelos, score de
confluencia, régimen, tipo de bot y optimizador de grid (rango, grids, SL/TP), todo cableado
en `bottom_dashboard.py`, `run_recommendation.py` y el panel web.
Sanity-check histórico: score **83/100** en el suelo de dic-2018, **82/100** en nov-2022
y **0/100** en el techo de 2021.
