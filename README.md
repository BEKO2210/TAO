## 🚀 ATLAS Agents — Start nächste Woche

Die auf diesem Repo aufbauende Plattform startet nächste Woche.

**Drei Wege, sie zu nutzen:**

1. **ATLAS kopieren** — handle parallel zum Autoresearch-System
   in diesem Repo. Live-Signale, Auto-Execution, volle
   Transparenz. Seit Launch +30 %.

2. **Eigenes bauen** — beschreibe eine Strategie in einfachem Englisch,
   backteste sie auf 18 Monaten echter Daten, deploye sie live.

3. **Marktplatz** — veröffentliche deinen Agenten und verdiene mit,
   wenn andere ihn kopieren.

SIMONS läuft bereits live auf Kalshi-Prediction-Markets.
60 % Trefferquote.

Als Dankeschön für all das Feedback, die Ideen und die
Unterstützung, die dieses Projekt geprägt haben — wir geben der
GitHub-Community 20 % Rabatt. Für immer, nicht nur den ersten Monat.

→ **[atlasagents.co](https://atlasagents.co)**
Code **GITHUB20** beim Checkout verwenden. Nur die ersten 100.

---

# ATLAS – Selbstverbessernde KI-Trading-Agenten

**Gebaut von [General Intelligence Capital](https://generalintelligencecapital.com)**

[Karpathys Autoresearch](https://github.com/karpathy/autoresearch) + [Soros' Reflexivität](https://en.wikipedia.org/wiki/Reflexivity_(social_theory)) + [MiroFish-Schwarmsimulation](https://github.com/666ghj/MiroFish), angewendet auf Finanzmärkte.

Die Agent-Prompts sind die Weights. Die Sharpe Ratio ist die Loss-Funktion. Keine GPU nötig.

⭐ 944 Stars · 202 Forks

---

## Was ist das?

ATLAS ist ein Framework für autonome KI-Trading-Agenten, die ihre eigenen Prompts durch Markt-Feedback verbessern, auf unterschiedlichen Marktregimen trainieren, neue Agenten erschaffen, sobald sie Wissenslücken erkennen, und reflexive Zukünfte simulieren, um auf das Kommende vorbereitet zu sein.

25+ Agenten debattieren täglich über Märkte – verteilt auf 4 Layer. Jede Empfehlung wird gegen reale Outcomes gescort. Der schlechteste Agent bekommt seinen Prompt umgeschrieben. Verbessert sich die Performance, überlebt der Git-Commit. Wenn nicht: `git revert`.

Läuft jetzt live mit echtem Kapital.

---

## Architektur

### Layer 1 – Macro (10 Agenten)

Zentralbank, Geopolitik, China, Dollar, Zinskurve, Rohstoffe, Volatilität, Emerging Markets, News-Sentiment, Institutional Flow.

Diese Agenten setzen das Regime. Risk-on oder Risk-off? Wie sieht der Makro-Hintergrund aus?

### Layer 2 – Sektor-Desks (7 Agenten)

Halbleiter, Energie, Biotech, Konsum, Industrie, Financials, plus ein Bloomberg-artiger Relationship-Mapper, der Lieferketten, Eigentümerstrukturen, Analyst-Coverage und Wettbewerbsdynamiken trackt.

### Layer 3 – Superinvestoren (4 Agenten)

* **Druckenmiller** – Macro/Momentum: Was ist der große asymmetrische Trade?
* **Aschenbrenner** – AI/Compute: Wer profitiert vom Capex-Zyklus?
* **Baker** – Deep Tech/Biotech: Wer hat echte IP-Burggräben?
* **Ackman** – Quality Compounder: Pricing Power + FCF + Katalysator?

### Layer 4 – Decision (4 Agenten)

* **CRO** – adversarialer Risk-Officer: greift jede Idee an, findet korrelierte Risiken
* **Alpha Discovery** – findet Namen, die niemand sonst genannt hat
* **Autonomous Execution** – wandelt Signale in dimensionierte Trades um
* **CIO** – synthetisiert alle vorherigen Layer, gewichtet nach Darwinian-Agent-Scores, trifft die finale Entscheidung

---

## Der Autoresearch-Loop

Inspiriert von [Karpathys Autoresearch](https://github.com/karpathy/autoresearch). Gleiches Muster, andere Domäne.

* System identifiziert den schwächsten Agenten anhand der rollierenden Sharpe Ratio
* Erzeugt eine gezielte Prompt-Modifikation
* Läuft 5 Handelstage damit
* Prüft, ob die Sharpe Ratio des Agenten sich verbessert hat
* Behalten (`git commit`) oder verwerfen (`git reset`)

Die Agent-Prompts sind die zu optimierenden Weights. Jeder Handelstag ist eine Trainingsiteration. Eine VM für 20 $/Monat ersetzt die H100.

**Darwinian-Weights:** Jeder Agent hat ein Gewicht zwischen 0,3 (Minimum) und 2,5 (Maximum). Top-Quartil-Agenten werden täglich um × 1,05 hochgewichtet. Bottom-Quartil um × 0,95 heruntergewichtet. Der CIO gewichtet die Inputs proportional zu diesen Scores. Gute Agenten werden lauter. Schlechte leiser.

---

## 18-Monats-Backtest-Ergebnisse

**Zeitraum:** September 2024 – März 2026 (378 Handelstage)

* Versuchte Prompt-Modifikationen: 54
* Überlebt (behalten): 16 (30 %)
* Verworfen: 37 (70 %)
* Rendite in der Deployment-Phase: **+22 % in 173 Tagen**
* Bester Einzel-Pick: **AVGO bei 152 $, gehalten für +128 %**

Das System hat eigenständig erkannt, dass sein eigener Portfolio-Manager (CIO) die schwächste Komponente war — und ihn auf das Minimum heruntergewichtet, bevor wir das Problem manuell diagnostizierten.

### Equity-Kurve

![Equity Curve](results/equity_curve.png)

---

## Agent-Spawning

Das System erkennt wiederkehrende Wissenslücken in seinen eigenen Debatten. Wenn derselbe blinde Fleck 3-mal oder mehr in 5 Tagen auftaucht, erzeugt es autonom einen neuen Spezialisten-Agenten mit neutralem Gewicht.

In einem 6-monatigen Spawning-Test (Jul–Dez 2024):
- 9 Agenten autonom gespawned — Credit Markets, Earnings-Kalender, Options Flow, Liquiditätsbedingungen, Positionierungsdaten, Earnings-Guidance, Retail-Sentiment, Technische Levels
- 3 sind ausgestorben (mehr als 20 Tage am Mindestgewicht festgesetzt)
- 6 haben die Darwinian-Selektion überlebt und das Maximum erreicht
- Null menschliche Beteiligung bei der Entscheidung, was wann erschaffen wird

Das System ist von 25 auf 31 Agenten gewachsen — basierend darauf, was es selbst als nicht gewusst erkannt hat.

---

## All Seasons (PRISM) – Regime-spezifisches Training

Wir trainieren nicht einen Satz Agenten und hoffen, dass er überall funktioniert. Wir trainieren separate Kohorten auf unterschiedlichen Marktregimen.

Gleiche Start-Agenten. Gleiche Vanilla-Prompts. Unterschiedliche evolutionäre Umgebungen. Vollständig unterschiedliche Überlebensinstinkte.

| Kohorte | Zeitraum | Rendite | Behaltene Mods | Wichtigste Erkenntnis |
|---------|----------|---------|-----------------|------------------------|
| Bull/Niedrige Vola | 2016–2018 | +7,7 % | 180/509 (35 %) | Vola-Longs schließen, sobald Events friedlich aufgelöst werden |
| Crisis (COVID) | 2020 Q1–Q2 | -13,1 % | 0/3 (0 %) | Crashes sind zu schnell für Autoresearch — Agenten müssen vortrainiert ankommen |
| Zinserhöhung | 2022–2023 | -30,2 % | 38/89 (43 %) | Nicht in Fed-Wochen flip-floppen — mindestens 15 Tage zwischen Reversals |
| Recovery | 2020 Q2–Q4 | -29,0 % | 0/1 (0 %) | Gleiches Problem wie Crisis — zu schnell für die Feedback-Schleife |
| Euphorie | 2021 | +14,3 % | 119/243 (49 %) | Momentum-Bestätigung vor Shorts, Conviction in politischen Krisen begrenzen |

**Konvergente Evolution:** Alle fünf Kohorten haben eigenständig dieselben Meta-Regeln entdeckt — Conviction begrenzen, VIX als Regime-Filter nutzen, harte Positionslimits durchsetzen, Risk-Management nie übersteuern. Niemand hat Vorsicht einprogrammiert. Jede Kohorte hat sie gelernt, indem sie bei Selbstüberschätzung Geld verloren hat.

**Divergente Evolution:** Derselbe Volatilitäts-Agent startete in jeder Kohorte mit 844 Bytes:
- Bull-Märkte: gewachsen auf 121.260 Bytes (143-fach). Hat gelernt: „Vola-Longs sofort schließen, wenn Events friedlich aufgelöst werden."
- Zinserhöhung: gewachsen auf 10.354 Bytes. Hat gelernt: „NIEMALS VXX kaufen, wenn der VIX zwischen 15 und 25 liegt."
- Euphorie: gewachsen auf 1.998 Bytes. Hat gelernt: „VIX über 30 ist Bedingung, bevor man Vola long geht."

Gleicher Agent. Gleicher Start-Prompt. Drei vollständig unterschiedliche Überlebensstrategien, geformt durch drei unterschiedliche Märkte.

---

## JANUS Meta-Layer

Mehrere trainierte Kohorten produzieren unterschiedliche Empfehlungen. JANUS sitzt über allen Kohorten und gewichtet sie algorithmisch nach jüngster Treffergenauigkeit.

Das Gewichtsdifferential zwischen den Kohorten ist ein emergenter Regime-Detektor:
- Wenn Short-Window-Agenten outperformen → **NOVEL REGIME**
- Wenn Long-Window-Agenten outperformen → **HISTORICAL REGIME**
- Wenn beide etwa gleichauf liegen → **MIXED**

Wir haben keinen Regime-Detektor gebaut. Er ist daraus entstanden, dass wir verfolgt haben, welche Kohorte richtig liegt.

---

## Soros-Reflexivitäts-Engine

Märkte spiegeln die Realität nicht nur — sie verändern sie. Wir haben reflexive Feedback-Schleifen ins Simulations-Framework eingebaut.

Fünf modellierte Feedback-Loops:
1. **Preis → Fundamentaldaten:** Aktiendrops > 15 % triggern Bonitätsabstufungen, Talent-Abwanderung, Capex-Kürzungen. Anstiege > 20 % triggern günstiges Kapital, Talent-Anziehung, Kunden-Vertrauen.
2. **P&L → Verhalten:** Drawdown eines Fonds > 10 % → erzwungene Verkaufskaskade. Gewinne > 15 % → größere Positionen und konzentrierte Wetten.
3. **Narrativ → Flows:** 3+ Analysten konvergieren auf eine These → Retail-Flow folgt. Gegenläufige Narrative entstehen nach längerem Konsens.
4. **Markt → Politik:** Aktien-Drawdown > 15 % → Zentralbank signalisiert Lockerung. Öl > 130 $ → Freigabe strategischer Reserven.
5. **Erkennung reflexiver Umkehrungen:** Feedback-Loop läuft 5+ Runden in eine Richtung → als reflexives Extrem markiert. Maximaler Konsens = maximale Fragilität.

Erste Detektion: Bullischer Gold-Konsens tauchte in 4 von 5 Simulationsrunden auf — geflaggt als überfüllter Trade mit 32 % Reversal-Wahrscheinlichkeit. Das ist Soros in Code.

---

## MiroFish-Schwarmsimulations-Integration

Integriert mit [MiroFish](https://github.com/666ghj/MiroFish), einer Schwarmintelligenz-Engine, die parallele digitale Welten mit Tausenden KI-Agenten erzeugt.

Unsere Trading-Agenten lernen nicht nur aus der Vergangenheit — sie trainieren auf simulierten Zukünften:

- Über Nacht generiert das System verzweigende Szenarien (geopolitische Eskalation, Fed-Politik, Earnings-Schocks, Black Swans)
- Tausende simulierter Agenten (Fondsmanager, Zentralbanker, Retail-Trader, Konzern-Vorstände) interagieren mit reflexivem Feedback
- ATLAS-Trading-Agenten werden in diesen simulierten Zukünften per derselben Darwinian-Loop trainiert
- Agenten, die simulierte Zukünfte gut navigieren, werden hochgewichtet
- Vorhersagen werden gegen tatsächliche Outcomes gescort, um die Simulationsgenauigkeit zu verbessern

**Erstes Ergebnis:** Druckenmiller-artiger Agent erreicht in simulierten Crashs einen Score von 1,0, in Melt-ups aber nur 0,22. Der Quality-Compounder-Agent ist genau umgekehrt. Das System weiß, welchen Instinkten es vertrauen kann, bevor das Regime eintritt — nicht erst danach.

---

## Kerneinsicht

Die Orchestrierungsschicht zählt genauso viel wie die Intelligenzschicht.

Einzelne Agenten haben sich durch Autoresearch messbar verbessert. Aber Portfolio-Renditen hängen davon ab, wie Agentensignale in dimensionierte Positionen übersetzt werden. Die Synthese-/Entscheidungs-Schicht ist der Bottleneck. Die Intelligenz einzelner Agenten zu verbessern, ohne die Orchestrierung zu verbessern, bringt abnehmende Erträge.

---

## Was enthalten ist

* Framework-Architektur und Pipeline-Struktur
* Autoresearch-Loop-Design
* Backtest-Ergebnisse und Equity-Kurve
* All-Seasons-(PRISM)-Methodik und -Ergebnisse
* Agent-Spawning-Mechanismus
* JANUS-Meta-Layer-Design
* Soros-Reflexivitäts-Engine
* MiroFish-Integrations-Bridge
* Beispielhafte Platzhalter-Prompts (generisch, untrainiert)

## Was NICHT enthalten ist

* Trainierte Agent-Prompts (proprietär — evolutionäres Produkt aus Markt-Feedback)
* Per-Regime evolvierte PRISM-Prompts
* CIO-Active-Management-Regeln
* Agent-Scorecard-Daten
* Live-Portfolio-Positionen
* Darwinian-Gewichtungswerte
* MiroFish-Simulations-Outputs

Die trainierten Prompts sind die Kern-IP. Ein Wettbewerber, der heute startet, ist Hunderte Iterationen zurück. Diese Lücke wächst jeden Tag.

---

## Tech-Stack

* **Agenten:** Claude Sonnet (Anthropic API)
* **Simulation:** MiroFish-Schwarm-Engine
* **Daten:** FMP, Finnhub, Polygon, FRED
* **Infrastruktur:** Azure VM (20 $/Monat)
* **Versionskontrolle:** Git-Feature-Branches für Autoresearch-Tracking
* **Kosten:** ca. 50–80 $ für den vollen 18-Monats-Backtest, ca. 30 $ für alle fünf PRISM-Kohorten

---

## Kontakt

**Chris Worsey** — CEO & Technical Founder, General Intelligence Capital

[chris@generalintelligencecapital.com](mailto:chris@generalintelligencecapital.com)

[generalintelligencecapital.com](https://generalintelligencecapital.com)
