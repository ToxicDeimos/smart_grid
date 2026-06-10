# smart_grid

Detector de **suelos de ciclo** de Bitcoin + **optimizador de grids de futuros** para Pionex.

El sistema responde a dos preguntas:

1. **¿Estamos en zona de suelo de ciclo?** — un termómetro 0–100 que combina señales de
   precio y on-chain en un score de confluencia.
2. **¿Qué bot de grid montar y con qué parámetros?** — tipo de bot (Long / Short / Neutral),
   zona de entrada / trigger, rango (límites inferior/superior), nº de grids, apalancamiento,
   SL/TP y **precio de liquidación** calculado.

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

**On-chain** (Coin Metrics Community API + APIs de hashrate, gratis):
- **MVRV Z-Score**
- **Realized Price** (precio < realized = capitulación)
- **Hash Ribbons** (capitulación de mineros + recuperación)
- **Puell Multiple** (ingresos de mineros)

---

## Instalación

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

No hace falta ninguna clave API en v1: todas las fuentes de datos son públicas/gratuitas.

## Uso

```bash
# Termómetro de suelo actual (cada señal + score 0-100, incluye la 200WMA de hoy)
python scripts/bottom_dashboard.py

# Recomendación completa de bot de grid para un capital dado
python scripts/run_recommendation.py --capital 2000 --symbol BTC/USDT

# Sanity-check de las señales contra los suelos historicos (2018, 2022)
python scripts/backtest_signals.py
```

## Estructura

```
src/
  data/        # ccxt (mercado) + Coin Metrics / hashrate (on-chain) + cache
  signals/     # señales de precio, on-chain y score de confluencia
  regime/      # tendencia vs rango
  grid/        # tipo de bot + optimizador de parametros
  liquidation.py  # precio de liquidacion del futures grid
  report.py    # ensambla la recomendacion
scripts/       # CLIs: bottom_dashboard, run_recommendation, backtest_signals
config/        # config.yaml (umbrales, pesos, fees)
tests/         # pytest
```

## Configuración

Todos los umbrales de señales, pesos del score, fees y restricciones de Pionex
(apalancamiento mínimo 3x) están en [`config/config.yaml`](config/config.yaml).

## Estado

En desarrollo (v1). Roadmap por fases en el historial de commits.
