# Disclaimer / Risikohinweis

**Dieses Repository ist ein Research- und Bildungsprojekt. Es ist KEINE Anlageberatung.**

## Wichtige Punkte

1. **Keine Performance-Garantie.** Der ATLAS-Backtest auf den im `results/`
   gespeicherten Daten zeigt eine **negative** Rendite über 18 Monate
   (-5,91 %). Die +30 %-Behauptung im Original-README stammt aus einer
   nicht öffentlichen Deployment-Phase, deren Code und Prompts dieses
   Repository NICHT enthält.

2. **Trainierte Prompts fehlen.** Die im Public-Repo enthaltenen Prompts
   sind generische Platzhalter. Die proprietären, durch Autoresearch
   evolvierten Prompts sind nicht enthalten und auch nicht reproduzierbar
   ohne wochenlange Trainingsläufe mit Live-Marktdaten.

3. **API-Kosten.** Ein einzelner EOD-Cycle ruft Claude rund 25-mal auf.
   Bei aktuellen Sonnet-Preisen entspricht das mehreren Dollar pro Tag.
   Backtests über Hunderte von Tagen können hohe Beträge erreichen.

4. **Reale Risiken bei Live-Trading.**
   - LLM-Halluzinationen können zu sinnlosen Trades führen.
   - Slippage, Spreads und Marktdrop sind in dieser Version
     nicht modelliert.
   - Forward-Returns aus yfinance sind ex-post adjustiert (Splits/
     Dividenden) und nicht point-in-time genau.

5. **Empfehlung.** Bevor du echtes Geld einsetzt:
   - Backteste mehrere Monate mit `--no-autoresearch`
     und mit aktivem Autoresearch.
   - Vergleiche die Ergebnisse mit einem einfachen Buy-and-Hold von SPY.
   - Wenn der Backtest nicht klar besser ist als SPY, **nicht** live gehen.
   - Wenn du live gehst, beginne mit einem **Paper-Trading-Konto** für
     mindestens 3 Monate.
   - Setze niemals Geld ein, dessen Verlust dich finanziell ernsthaft
     gefährden würde.

## Lizenz

MIT — siehe `LICENSE`.
