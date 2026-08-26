# ASH data-source contract

Every observation stores both the source timestamp and the time ASH first saw
it. Missing, stale, malformed, or entitlement-denied data is unavailable; it is
never imputed as a live observation.

## Execution-critical

### Alpaca paper trading API

- Purpose: account, positions, option contracts, and paper orders.
- Safety: broker URLs are permanently restricted to the Alpaca paper origin.
- Failure: new entries fail closed. Existing exit intents continue retrying
  under the desk’s reconciliation rules.

### Alpaca market data, IEX equities

- Purpose: stock bars, snapshots, and the underlying state.
- Limitation: IEX is a small subset of consolidated US volume. RVOL and tape
  features must be labeled `iex`, not “the market.”
- Failure: stale or incomplete state blocks affected entries.

### Alpaca indicative options

- Purpose: option contracts, bid/ask, volume, open interest, and prospective
  path labels.
- Limitation: paper fills and indicative quotes do not prove executable returns.
- Failure: zero bid, missing ask, crossed/stale quote, wide spread, or missing
  exact same-day expiry blocks the candidate.

## Required NLP path

### Home ASH NLP service

- Purpose: event class, finance sentiment, novelty, confidence, and model
  provenance.
- Transport: Tailscale private address plus HMAC request signing.
- Failure: news-sensitive strategies block. Quantitative strategies, exits,
  reconciliation, heartbeat, and risk controls continue independently.
- Storage: content hashes and structured outputs are retained. Full article
  bodies are not required.

### Alpaca headlines

- Purpose: primary timestamped headline input to the home NLP service.
- Failure: no headline is not neutral sentiment; NLP-dependent setups abstain.

## Free research enrichments

### SEC EDGAR

- Endpoints: `data.sec.gov/submissions` and XBRL company facts.
- Authentication: no key; an identifying User-Agent with contact email is
  mandatory.
- Fair access: remain below the SEC’s published aggregate limit and cache
  aggressively.
- Use: filing events and point-in-time fundamentals, not millisecond execution.

### FRED and ALFRED

- Use: macro observations, releases, and vintages.
- Backtests must use values available at the historical decision time. Final
  revised FRED values may not be substituted for ALFRED vintages.

### GDELT DOC 2

- Use: broad headline discovery and event context.
- Limitation: duplicated, translated, delayed, or weakly mapped articles are
  expected. Deduplicate by normalized content/source and require source time.
- Failure: optional enrichment only; never substitute it for an unavailable
  execution-critical quote.

### Alpha Vantage free tier

- Use: low-frequency daily sentiment/fundamental enrichment when quota permits.
- Limitation: the free request budget and market-data entitlements are not
  suitable for the live execution path.

Provider limits and terms can change. Each adapter must expose health, quota,
latency, stale state, and its version. Startup capability checks disable only
the dependent feature or strategy.
