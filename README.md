# TAO — ATLAS Trading Agents (Fork & Extension)

> **Fork von [chrisworsey55/atlas-gic](https://github.com/chrisworsey55/atlas-gic)**
> Lizenz: MIT (Original-Copyright bei General Intelligence Capital, siehe `LICENSE`).
> Dieses Repo erweitert das Original um die fehlenden Laufzeit-Module,
> sodass es tatsächlich ausführbar ist. Alle Änderungen sind ehrlich
> dokumentiert. Bitte vor Nutzung `DISCLAIMER.md` lesen.

---

## Was ist ATLAS?

Ein 4-Layer-Multi-Agenten-Framework für Trading-Entscheidungen, basierend auf:
- [Karpathys Autoresearch](https://github.com/karpathy/autoresearch) — Agent-Prompts werden als „Weights" behandelt und durch Markt-Feedback optimiert.
- [Soros' Reflexivität](https://en.wikipedia.org/wiki/Reflexivity_(social_theory)) — Märkte verändern Realität, nicht nur umgekehrt.
- [MiroFish](https://github.com/666ghj/MiroFish) — Schwarmsimulation für Future-Scenarios.

25 Agenten debattieren täglich in 4 Layern, jede Empfehlung wird gegen reale Forward-Returns gescort, der schwächste Agent bekommt seinen Prompt durch ein LLM modifiziert. Verbessert sich die rollierende Sharpe Ratio in 5 Tagen → `git merge`. Sonst → Branch verworfen.

---

## Status dieses Forks

### Was war im Original-Repo

| Bereich | Inhalt |
|--------|--------|
| `architecture/` | Designdokumente (Overview, 4 Layer, Autoresearch-Loop) |
| `prompts/examples/` | 4 generische Beispiel-Prompts |
| `results/` | 18-Monats-Backtest-Daten (`summary.json`, `autoresearch_log.json`, `equity_curve.png`, `portfolio_trajectory.csv`) |
| `src/janus.py` | Meta-Layer für Cohort-Blending + Regime-Detector |
| `src/mirofish/` | 5 Python-Module für Schwarmsimulation, **referenzieren aber `config.settings`, `data.macro_client`, `data.price_client`** |
| `src/README.md` | Beschreibt eine Architektur, die im Public-Repo NICHT enthalten war |

### Was im Original-Repo gefehlt hat

Der `src/README.md` referenziert eine ganze `src/agents/`-Struktur (`backtest_loop.py`, `eod_cycle.py`, `market_data.py`, `scorecard.py`, `autoresearch.py`), `src/data/`-Clients, `src/config/settings.py`, `src/utils/`-Helfer und 25 trainierte Agent-Prompts. **Nichts davon war im Public-Repo enthalten** — `janus.py` und `mirofish/*.py` waren also gar nicht ausführbar.

### Was dieser Fork hinzugefügt hat

**5 Hauptmodule (`src/agents/`):**
| Modul | Aufgabe |
|------|---------|
| `registry.py` | Statische Specs für alle 25 Agenten + Helpers |
| `market_data.py` | Bündelt Price + Macro mit Disk-Caching |
| `scorecard.py` | Recommendation-Log, rollierende Sharpe Ratio, Hit-Rate, Darwinian-Weight-Update (Top-Quartil ×1,05, Bottom ×0,95) |
| `eod_cycle.py` | Parallele 4-Layer-Pipeline (ThreadPoolExecutor pro Layer) |
| `autoresearch.py` | Claude generiert Prompt-Modifikation auf Feature-Branch, 5-Tage-Test, `merge` oder Branch-Drop |
| `backtest_loop.py` | Pro-Tag-Iteration: Score → Cycle → Weights → Autoresearch → Execute |

**Infrastruktur (`src/config/`, `src/data/`, `src/utils/`):**
- `config/settings.py` — env-getriebene Konfiguration, Pfade, Limits
- `data/price_client.py`, `data/macro_client.py` — yfinance-Wrapper (kostenlos, kein API-Key nötig)
- `utils/llm.py` — Anthropic-SDK mit Retries, JSON-Parsing, Prompt-Caching
- `utils/git_ops.py` — Branch / commit / merge / reset für Autoresearch
- `utils/logging_utils.py` — strukturierter Logger

**25 Agent-Prompts (`src/prompts/`):**
- `macro/` (10): central_bank, geopolitical, china, dollar, yield_curve, commodities, volatility, emerging_markets, news_sentiment, institutional_flow
- `sector/` (7): semiconductor, energy, biotech, consumer, industrials, financials, relationship_mapper
- `superinvestor/` (4): druckenmiller, aschenbrenner, baker, ackman
- `decision/` (4): cro, alpha_discovery, autonomous_execution, cio

Diese Prompts sind **generische Ausgangs-Prompts**, kein Ersatz für die proprietären, durch echtes Trading evolvierten Prompts. Sie sind das Substrat, das Autoresearch über Wochen/Monate mutiert.

**Top-Level:**
- `src/cli.py` — Subcommands: `snapshot`, `cycle`, `backtest`, `score`, `weights`, `autoresearch`, `status`
- `requirements.txt`, `.env.example`, `.gitignore`
- `QUICKSTART.md` — Setup + Architektur-Diagramm
- `DISCLAIMER.md` — Risikohinweise

**Build-Zahlen:** 49 neue Dateien, ~2.800 Zeilen Code + Prompts. Alle 12 Python-Module importieren clean, alle 25 Prompt-Dateien werden vom Registry geladen, Weight-Init liefert 25 Einträge.

---

## Ehrliche Ergebnisse

### Original-Backtest (chrisworsey55/atlas-gic)

`results/summary.json` zeigt:
- **Zeitraum:** 2024-09-01 bis 2026-03-07 (378 Handelstage)
- **Start:** 1.000.000 $ → **Ende:** 940.937,77 $
- **Total Return: −5,91 %**
- 54 Autoresearch-Modifikationen versucht, 16 (30 %) behalten
- Final wurde der CIO-Agent auf das Mindestgewicht 0,3 abgestuft — das System hat seinen eigenen Portfolio-Manager als schwächstes Glied erkannt.

### Die +30 %-Behauptung im Original

Das Original-README erwähnt „+22 % in 173 Tagen Deployment-Phase" und „Up 30 % since launch". Diese Zahlen stammen aus einer **nicht öffentlichen Live-Phase**, deren Code, Prompts und Trades nicht in diesem Repo (und nicht im Original-Repo) liegen. Nicht reproduzierbar, nicht verifizierbar.

### Was dieser Fork an Performance hat

**Null verifizierbare Performance.** Wir haben das System lauffähig gemacht. Wir haben es noch nicht über einen Backtest-Zeitraum laufen lassen, der Aussagen erlauben würde. Das ist die nächste Aufgabe (siehe unten).

---

## Architektur

```
Layer 1 (Macro, 10 Agenten)        → Regime: RISK_ON / RISK_OFF / NEUTRAL
        ↓
Layer 2 (Sector Desks, 7)          → Sector-Picks (Long/Short pro Sektor)
        ↓
Layer 3 (Superinvestoren, 4)       → Philosophie-gefilterte Ideen
        ↓
Layer 4 (CRO + Alpha + Exec + CIO) → Portfolio-Aktionen
```

Details: `architecture/overview.md`, `architecture/layers.md`, `architecture/autoresearch.md`.

Codestruktur und CLI-Befehle: `QUICKSTART.md`.

---

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env       # ANTHROPIC_API_KEY eintragen

python src/cli.py snapshot                       # Macro+Preise (kein API-Key)
python src/cli.py cycle                          # 1 Tag, ~25 Claude-Calls
python src/cli.py backtest 2025-01-02 2025-01-31 # Backtest-Range
python src/cli.py status                         # Zähler
```

Vollständige Anleitung in `QUICKSTART.md`.

---

## Was als Nächstes gemacht wird

Reihenfolge nach erwartetem Wert / Risiko:

1. **Daten-Robustheit.** yfinance ist gratis aber unzuverlässig. Mindestens FMP oder Polygon als zweite Quelle anbinden, point-in-time-fähig, mit Cross-Validation.
2. **Realistischer Backtest.** Mehrmonatigen Walk-Forward-Backtest gegen SPY-Buy-and-Hold. Klar dokumentiertes Setup, klar berichtete Ergebnisse — auch wenn sie schlecht sind.
3. **Paper-Trading-Modus.** Bevor irgendwas live läuft: 3+ Monate Paper-Trading mit echten EOD-Cycles, voller Logging.
4. **MiroFish-Bridge sauber anschließen.** Die `src/mirofish/*.py`-Module liegen drin, sind aber bisher nicht in den `eod_cycle` integriert. Future-Scenarios als Layer-0-Input wäre die natürliche Stelle.
5. **JANUS-Integration.** `src/janus.py` blendet mehrere Cohorts. Sobald wir einen ersten Cohort durchtrainiert haben, einen zweiten auf anderem Regime trainieren und JANUS aktivieren.
6. **Prompt-Caching für Layer 1.** Die 10 Macro-Prompts sind statisch — `cache_control` bringt hier real Geld.
7. **Slippage- und Spread-Modell** im Backtest.
8. **Live-Execution-Stub.** Aktuell schreibt `backtest_loop` nur ins Portfolio-File. Für Live nötig: Broker-Adapter (Interactive Brokers, Alpaca) hinter `autonomous_execution`.

---

## Was NICHT enthalten ist

- Trainierte / evolvierte Agent-Prompts (das eigentliche IP)
- PRISM-Cohorts (Bull / Crisis / Rate-Tightening / Recovery / Euphoria)
- Live-Portfolio-Daten oder Darwinian-Weight-Werte aus echtem Betrieb
- Broker-Anbindung
- Order-Routing oder Execution-Algorithmen
- Garantien jeglicher Art

---

## Tech-Stack (wie tatsächlich implementiert)

- **LLM:** Claude Sonnet 4.6 (Default), Opus 4.7 (Premium) via Anthropic API mit Prompt-Caching
- **Marktdaten:** yfinance (Default, kostenlos). Stubs für FMP / Finnhub / Polygon / FRED über `.env`-Variablen vorbereitet, aber nicht aktiv verdrahtet.
- **Persistenz:** JSON-Dateien in `src/data/state/`
- **Versionskontrolle:** Git-Feature-Branches für Autoresearch
- **Parallelisierung:** `ThreadPoolExecutor` pro Layer
- **Infrastruktur:** Lokal lauffähig, kein Cloud-Deployment in diesem Repo

---

## Risikohinweis (kurz)

**Dieses System wird dich nicht reich machen.** Der dokumentierte Backtest war negativ. Trainierte Prompts fehlen. Live-Trading-Risiken sind real. Lies `DISCLAIMER.md`.

Wenn du echtes Geld einsetzen willst:
1. Mindestens 3 Monate Paper-Trading.
2. Vergleich mit SPY-Buy-and-Hold. Wenn nicht klar besser → nicht live.
3. Niemals Geld einsetzen, dessen Verlust dich finanziell trifft.

---

## Credits

- **Original-Framework:** Chris Worsey, General Intelligence Capital — [`chrisworsey55/atlas-gic`](https://github.com/chrisworsey55/atlas-gic)
- **Inspiration:** Andrej Karpathy ([autoresearch](https://github.com/karpathy/autoresearch)), George Soros (Reflexivität), MiroFish ([666ghj/MiroFish](https://github.com/666ghj/MiroFish))
- **Lizenz:** MIT — siehe `LICENSE`. Die MIT-Lizenz des Originals erlaubt Modifikation und Distribution; Copyright-Notiz wurde unverändert übernommen.
- **Diese Erweiterung:** auf Branch `claude/copy-map-atlas-gic-TXKCe` in [`beko2210/tao`](https://github.com/BEKO2210/TAO).

Wenn etwas in dieser README unklar oder falsch dokumentiert ist: Issue aufmachen, ich korrigiere es.
