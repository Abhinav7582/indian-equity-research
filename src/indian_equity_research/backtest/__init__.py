"""Backtesting.

Built so that it can catch itself lying. Three acceptance tests govern this
package and every one of them is a way of failing on purpose:

* a deliberately leaked feature must produce an absurd result - if tomorrow's
  return as a signal yields a merely *plausible* Sharpe, the engine is broken;
* a random signal must lose **exactly** the modelled cost, proving costs are
  applied rather than quietly skipped;
* a hand-calculated example must reproduce to the rupee.

A backtester that cannot fail those cannot be trusted when it succeeds.
"""
