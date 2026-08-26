# ASH learning research basis

This document records why a feature exists and what the implementation may
claim. A citation is not evidence that an ASH implementation is profitable.
Every signal still requires chronological, cost-aware out-of-sample evidence.

## Momentum and reversal

- Jegadeesh and Titman, “Returns to Buying Winners and Selling Losers,”
  *Journal of Finance* (1993), DOI: 10.1111/j.1540-6261.1993.tb04702.x.
- Daniel and Moskowitz, “Momentum Crashes,” *Journal of Financial Economics*
  (2016), DOI: 10.1016/j.jfineco.2015.12.002.
- Lehmann, “Fads, Martingales, and Market Efficiency,” *Quarterly Journal of
  Economics* (1990), DOI: 10.2307/2937816.
- Nagel, “Evaporating Liquidity,” *Review of Financial Studies* (2012),
  DOI: 10.1093/rfs/hhs066.

ASH uses lagged returns, drawdown, volatility, and liquidity as conditional
features. It does not translate a positive trailing return directly into a call
or assume a short reversal survives option spread and theta costs.

## Volatility pricing

- Bakshi and Kapadia, “Delta-Hedged Gains and the Negative Market Volatility
  Risk Premium,” *Review of Financial Studies* (2003),
  DOI: 10.1093/rfs/hhg002.
- Carr and Wu, “Variance Risk Premiums,” *Review of Financial Studies* (2009),
  DOI: 10.1093/rfs/hhn038.
- Goyal and Saretto, “Cross-Section of Option Returns and Volatility,”
  *Journal of Financial Economics* (2009),
  DOI: 10.1016/j.jfineco.2009.01.001.

Sparse indicative chains cannot reproduce model-free variance-premium research.
ASH may use implied-versus-realized volatility proxies, but it must label them
as approximations and may not authorize naked short options.

## Earnings, events, and language

- Ball and Brown, “An Empirical Evaluation of Accounting Income Numbers,”
  *Journal of Accounting Research* (1968), DOI: 10.2307/2490232.
- Bernard and Thomas, “Post-Earnings-Announcement Drift,” *Journal of
  Accounting Research* (1989), DOI: 10.2307/2491062.
- Tetlock, “Giving Content to Investor Sentiment,” *Journal of Finance* (2007),
  DOI: 10.1111/j.1540-6261.2007.01232.x.
- Loughran and McDonald, “When Is a Liability Not a Liability?” *Journal of
  Finance* (2011), DOI: 10.1111/j.1540-6261.2010.01625.x.
- Tetlock, “All the News That’s Fit to Reprint,” *Review of Financial Studies*
  (2011), DOI: 10.1093/rfs/hhq141.

Headline tone is a weak conditional feature. ASH also records event class,
source time, observation time, novelty, confidence, and model version. NLP
cannot fire alone. Without timestamped analyst expectations and actual results,
the system calls a headline an earnings event, not a measured PEAD surprise.

## Regimes, calibration, and drift

- Hamilton, “A New Approach to the Economic Analysis of Nonstationary Time
  Series and the Business Cycle,” *Econometrica* (1989), DOI: 10.2307/1912559.
- Brier, “Verification of Forecasts Expressed in Terms of Probability,”
  *Monthly Weather Review* (1950),
  DOI: 10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2.
- Gama et al., “A Survey on Concept Drift Adaptation,” *ACM Computing Surveys*
  (2014), DOI: 10.1145/2523813.
- Bifet and Gavaldà, “Learning from Time-Changing Data with Adaptive
  Windowing,” *SDM* (2007), DOI: 10.1137/1.9781611972771.42.

ASH uses observable soft context rather than claiming a latent regime is true.
Each horizon reports Brier score and reliability. Predictions are made before
labels and models update only after the complete horizon resolves. Drift
demotes risk; it never grants promotion.

## Costs and multiple testing

- Phillips and Smith, “Trading Costs for Listed Options,” *Journal of Financial
  Economics* (1980), DOI: 10.1016/0304-405X(80)90016-1.
- Muravyev and Pearson, “Options Trading Costs Are Lower than You Think,”
  *Review of Financial Studies* (2020), DOI: 10.1093/rfs/hhaa010.
- White, “A Reality Check for Data Snooping,” *Econometrica* (2000),
  DOI: 10.1111/1468-0262.00152.
- Hansen, “A Test for Superior Predictive Ability,” *Journal of Business &
  Economic Statistics* (2005), DOI: 10.1198/073500105000000063.
- Harvey, Liu, and Zhu, “…and the Cross-Section of Expected Returns,” *Review
  of Financial Studies* (2016), volume 29, pages 5–68.
- Bailey and López de Prado, “The Deflated Sharpe Ratio,” *Journal of Portfolio
  Management* (2014), volume 40 issue 5.

Baseline labels buy at ask and exit at bid. Midpoint and paper fills are
diagnostics, not proof of execution. Validation uses expanding chronological
folds, payoff-overlap removal, horizon embargoes, an untouched final period,
day/event-cluster resampling, and an immutable registry of attempted models.

## Claims prohibited by current data

- A proven profitable 0DTE strategy from the available free history.
- Consolidated order flow from IEX volume.
- A model-free variance premium from sparse option quotes.
- Executable returns inferred from midpoint or Alpaca paper fills.
- Guaranteed “right trades” or a pooled model that treats all horizons alike.
