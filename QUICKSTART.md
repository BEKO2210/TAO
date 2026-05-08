# Quickstart

## 1. Installation

```bash
pip install -r requirements.txt
```

## 2. Konfiguration

```bash
cp .env.example .env
# .env öffnen und ANTHROPIC_API_KEY eintragen
```

API-Key gibt's auf https://console.anthropic.com/

## 3. Smoke-Test (ohne API-Key)

```bash
python src/cli.py snapshot
```

Sollte einen JSON-Dump von Macro + Preisen via yfinance ausgeben. Wenn das
funktioniert, ist die Datenpipeline ok.

## 4. Einen einzelnen Daily-Cycle laufen lassen (braucht API-Key)

```bash
python src/cli.py cycle
```

Ruft alle 25 Agenten auf (≈ 25 Claude-Calls), schreibt das Ergebnis nach
`src/data/state/cycles/<cycle_id>.json` und loggt jede Agent-Empfehlung.

### Mock-Modus (kostenlos, ohne API-Key)

```bash
python src/cli.py cycle --mock
python src/cli.py backtest 2025-01-02 2025-01-31 --mock
LLM_MODE=mock python src/cli.py cycle
```

Erzeugt deterministische, agent-bewusste synthetische Outputs. Die Pipeline,
das Scoring, die Darwinian-Weights und Autoresearch laufen wie im Live-Modus
— nur mit synthetischen Agent-Outputs statt echter Claude-Calls. **Bitte
beachten:** Mock-Outputs erzeugen keinen echten Alpha — sie testen nur die
Plumbing.

## 5. Kurzen Backtest laufen lassen

```bash
python src/cli.py backtest 2025-01-02 2025-01-10
```

Iteriert über die Handelstage, scort vorherige Empfehlungen, aktualisiert
Darwinian-Weights, läuft Autoresearch. Schreibt parallel ein
SPY-Buy-and-Hold-Benchmark mit (`src/data/state/benchmark_trajectory.json`)
und gibt am Ende eine Tabelle mit Sharpe / Sortino / Max-DD / Alpha vs SPY
aus.

Mit `--no-autoresearch` kann der Selbstmodifikations-Loop deaktiviert
werden, mit `--no-reset` wird der vorhandene Portfolio-State weitergenutzt
(Fortsetzungs-Backtest).

## 6. Performance-Metriken

```bash
python src/cli.py metrics      # Tabelle Strategy vs SPY
python src/cli.py reset        # State löschen, frischer Start
```

## 7. Status & Score

```bash
python src/cli.py status      # Zähler
python src/cli.py weights     # aktuelle Darwinian-Gewichte
python src/cli.py score       # Forward-Returns nachziehen + Sharpes
```

## 8. Eine Autoresearch-Iteration manuell auslösen

```bash
python src/cli.py autoresearch
python src/cli.py autoresearch --mock   # ohne API-Kosten
```

Wenn ein offenes Experiment fällig ist, wird es ausgewertet (gehalten
oder verworfen). Sonst wird der Agent mit der niedrigsten Sharpe Ratio
ausgewählt und Claude generiert eine Prompt-Modifikation auf einem
Feature-Branch (`autoresearch/<agent>-<timestamp>`).

## Architektur — kurze Übersicht

```
src/
├── cli.py               ← entry point
├── config/settings.py   ← API-Keys, Pfade, Konstanten
├── data/
│   ├── price_client.py  ← yfinance wrapper (kostenlos)
│   ├── macro_client.py  ← VIX / Yields / Commodities via yfinance
│   └── state/           ← persistenter Zustand (JSON)
├── utils/
│   ├── llm.py           ← Anthropic SDK + JSON-Parsing + Prompt-Caching
│   ├── git_ops.py       ← Branch / commit / merge / reset für Autoresearch
│   └── logging_utils.py
├── agents/
│   ├── registry.py      ← die 25 Agenten als AgentSpecs
│   ├── market_data.py   ← gebündelter Datenzugriff
│   ├── scorecard.py     ← Sharpe, Hit-Rate, Darwinian-Update
│   ├── eod_cycle.py     ← 4-Layer-Pipeline (Macro → Sector → Super → Decision)
│   ├── autoresearch.py  ← LLM-driven prompt mod auf Git-Branch
│   └── backtest_loop.py ← Hauptrunner
├── prompts/
│   ├── macro/   (10 Prompts)
│   ├── sector/  (7)
│   ├── superinvestor/  (4)
│   └── decision/  (4)
├── janus.py             ← Meta-Layer für Multi-Cohort (aus Original)
└── mirofish/            ← Schwarmsimulation (aus Original)
```

## Was passiert in einem Cycle

1. **Layer 1 — 10 Macro-Agenten** parallel. Jeder gibt BULLISH/BEARISH/NEUTRAL
   plus Tickers. Aggregiert mit Darwinian-Weights → Regime-Label.
2. **Layer 2 — 7 Sector-Desks** parallel mit Regime-Kontext.
3. **Layer 3 — 4 Superinvestoren** filtern Sector-Picks nach Philosophie.
4. **Layer 4 — CRO + Alpha + Execution + CIO**. CRO greift jede Idee an,
   CIO synthetisiert.
5. CIO-Aktionen werden ins Portfolio übernommen, Forward-Returns getrackt.

Nach jedem Cycle:
- Darwinian-Weights werden aktualisiert (Top-Quartil × 1,05, Bottom × 0,95).
- Eine Autoresearch-Iteration läuft: schwächster Agent bekommt
  Prompt-Modifikation auf einem Branch, nach 5 Tagen Vergleich, dann
  Merge oder Branch-Drop.

## Gotchas

- yfinance ist gratis aber unzuverlässig in Live-Latenz. Für Echtzeit-Trading
  müsstest du `data/price_client.py` durch FMP/Polygon/Finnhub ersetzen.
- Die `forward_return`-Berechnung im Backtest nutzt aktuelle (split-adjusted)
  Daten — kein Point-in-Time. Kleine Verzerrung im Backtest.
- Autoresearch committet auf den aktuellen Branch und merged dort zurück.
  In Produktion nicht auf `main` arbeiten.

Siehe `DISCLAIMER.md` für die Risikohinweise. Bitte lies das, bevor du
echtes Geld an dieses System gibst.
