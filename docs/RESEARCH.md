# Investigación: ¿tienen edge los grid bots de futuros en BTC?

Este documento resume una investigación cuantitativa exhaustiva sobre si los grid bots
(Pionex) pueden generar un edge rentable en BTC, y a qué conclusión se llegó. Todos los
scripts citados están en `scripts/`.

## TL;DR

- **Ningún grid bate a comprar y mantener BTC.** Ni futuros ni spot, ni direccional ni neutral.
- El **edge real de BTC es su drift alcista** (~+7.6%/90d histórico). El grid lo **destruye**:
  el apalancado por la cola de liquidación, el spot por vender su BTC demasiado pronto.
- **Lo único que SÍ aporta valor: DCA inteligente** — acumular BTC spot ponderando las compras
  por el score de suelo de ciclo. Bate al DCA plano (+71.5% vs +50.4% ROI, 2021-2026).

## Metodología

- Simulación de grid sobre OHLCV **1h con recorrido intra-barra** (high/low), modelando la
  posición inicial direccional como Pionex (ver `src/backtest/grid_sim.py`).
- **Walk-forward**: en N fechas históricas se genera la recomendación con datos *hasta* esa
  fecha y se simula el periodo siguiente.
- **Validación out-of-sample**: in-sample (<2024) vs out-of-sample (≥2024). Una regla que solo
  funciona in-sample es overfitting.

## Resultados — grids direccionales

Nueve enfoques para dar dirección/timing a un grid de futuros 3x. **Cero con edge robusto OOS:**

| Enfoque | Script | Veredicto OOS |
|---|---|---|
| Entrar en cualquier precio | `backtest_grids.py` | Negativo |
| Timing RSI (dip-long / rip-short) | `grid_entry_timing.py` | dip-long mal; rip-short +7.6% pero n=9 |
| Confluencia EMA50 + rechazo | `grid_entry_timing.py` | **Overfitting** (bien in, mal out) |
| Soportes/Resistencias (swing+cluster) | `backtest_sr_grid.py` | long sin edge; short overfitting |
| Time-series momentum (30/90/180d) | `grid_momentum.py` | Ruido (inconsistente in/out) |
| Trigger en retroceso a soporte | `grid_pullback_entry.py` | Mejora media pero sin edge (22% acierto) |
| Retroceso de Fibonacci (0.382/0.5/0.618) | `grid_fibonacci.py` | **Overfitting** (Fib 0.5: in +3.3 / out −2.4) |
| Filtros de dirección + SL ajustado | `grid_strategy_test.py` | No rescatan |
| Confluencia bloque + EMA200 | `backtest_block_ema.py` | **El peor**: −17% (vs −5.9% sin filtro) |
| Gann (ángulos) | — | Descartado: dependen de escala, no testeable |

**Patrón común:** en todos, los aciertos fueron 40–73% pero la media negativa. La señal acierta
la mayoría de las veces; la **cola apalancada** (−60/−90% al fallar) se come las ganancias.

## Resultados — grids neutral y spot

- **Grid neutral 3x** (`backtest_grids.py`): el más robusto de los grids (+0.39%, 19/19 rentable)
  pero **modesto**, y por debajo del buy&hold.
- **Grid spot 1x** (`backtest_spot_grid.py`): **−1.15% vs +7.60% del buy&hold**. El grid spot
  vende su BTC en las subidas y se pierde el drift; tiene menos drawdown pero mucho menos retorno.

## Conclusiones estructurales (por qué no hay edge)

1. **Los niveles técnicos de BTC son trampas.** Soportes, resistencias, Fibs, EMA200: el precio
   los atraviesa más veces de las que los respeta (aciertos del 13–29% en las pruebas de S/R y
   Fib). BTC es **tendencial y eficiente**, no de rango.
2. **El apalancamiento es el enemigo.** Convierte cada error en una cola de −60/−90%. Un grid
   direccional 3x necesitaría ~80%+ de acierto sostenido, imposible en un mercado eficiente.
3. **El grid regala el drift.** El edge de BTC es subir a largo plazo; el grid vende pronto y
   renuncia a ello. Comprar y mantener lo captura entero.

## El hallazgo positivo: DCA inteligente

`backtest_dca.py` — compra semanal de BTC spot (2021-2026):

| Estrategia | Precio medio | ROI |
|---|---|---|
| DCA plano | $41,843 | +50.4% |
| **DCA inteligente** (×score, 1x-3x) | **$36,702** | **+71.5%** |
| Lump sum | — | +96.7% |

Ponderar las compras por el **score de suelo de ciclo** (más barato → más compra) logra un
precio medio **−12.3%** y **+21 pts** de ROI sobre el DCA plano. *(Lump sum gana a ambos por el
drift, pero solo aplica si tienes el capital de golpe; para aportaciones periódicas, el DCA
inteligente es la herramienta correcta.)* Implementado en `src/dca.py` y `scripts/run_dca.py`.

## Lecciones metodológicas

- **Valida out-of-sample siempre.** Varias estrategias (confluencia EMA50, Fib 0.5, short-rebote)
  brillaron in-sample y se derrumbaron fuera.
- **Más indicadores ≠ más edge.** Con N pequeño (pocos ciclos de BTC), añadir features aumenta el
  overfitting. La confluencia (2 indicadores) overfitteó; el RSI solo generalizó algo mejor.
- **Cuidado con el data mining.** Probar estrategia tras estrategia garantiza encontrar un falso
  positivo por azar. El número de hipótesis probadas importa.
- **Verifica el modelo contra la fuente.** Un bug en el simulador (no modelar la posición inicial
  de long/short) sesgó el veredicto hasta que se corrigió contra la documentación de Pionex.
