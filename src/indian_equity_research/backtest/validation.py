"""Purged, embargoed walk-forward cross-validation.

The problem this exists to prevent
----------------------------------
Ordinary k-fold cross-validation is invalid on time series, and invalid in a
direction that flatters. Two mechanisms, routinely conflated:

**Backward-looking features.** A signal computed on 2020-06-30 from a
126-session window is a function of every session back to roughly 2019-12-20.
Under *k-fold*, where a training fold can sit after a test fold, that window
reaches into data the model is about to be scored on.

**Forward-spanning outcomes.** An observation at *t* whose result is only known
at *t + h* -- a position held for h sessions, a label defined over the next
month -- contains information from the whole of ``[t, t + h]``. If *t* is in
training and *t + h* is in the test window, the training set already contains
the answer.

**These are not the same problem, and walk-forward solves only the first.**
Because every training session here precedes every test session, a
backward-looking feature computed in training can never reach the test period.
It cannot leak. What survives walk-forward is the second mechanism, and it is
the one this module purges: the last ``horizon`` training observations are
dropped, because their outcomes extend past the boundary.

Stating that plainly matters. A purge sized to the *feature lookback* rather
than the *outcome horizon* protects against a leak that walk-forward has
already ruled out, while leaving the real one untouched -- and it looks
identical from the outside.

**Serial correlation past the boundary.** Purging fixes the mechanical overlap
but not the statistical one: volatility clusters and momentum persists, so the
sessions either side of a boundary remain informative about each other even
when no observation spans it. *Embargoing* drops a further buffer.

Both devices are from López de Prado, *Advances in Financial Machine Learning*
(2018), ch. 7. The names are his; the failure they describe is older.

Why walk-forward and not k-fold
-------------------------------
Even purged, a k-fold split trains on the future to predict the past. That is
not a mistake a live system can make, so a result obtained that way does not
describe anything achievable. Every split here trains strictly before it tests.

What this module does not do
----------------------------
It splits time. It does not fit, score, or select. Selection is what the trial
register in ``HYPOTHESES.md`` governs and what
:func:`~indian_equity_research.backtest.gates.probability_of_backtest_overfitting`
measures. Keeping them apart matters: a splitter that also scored would make it
easy to run many splits and report the best, which is the very thing the gates
exist to catch.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Final

__all__ = [
    "DEFAULT_EMBARGO_FRACTION",
    "SplitError",
    "WalkForwardSplit",
    "purged_walk_forward",
    "sessions_between",
]

# López de Prado suggests an embargo of roughly 1% of the sample. It is a rule
# of thumb, not a result, and it is exposed as an argument for that reason. What
# is *not* negotiable is that it be fixed before any result is read -- an
# embargo tuned until the answer improves is a free parameter dressed as rigour.
DEFAULT_EMBARGO_FRACTION: Final = 0.01


class SplitError(ValueError):
    """Raised when a valid split cannot be produced from the input."""


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    """One train/test division of a session list.

    Attributes:
        train: Sessions to fit on. Already purged and embargoed.
        test: Sessions to score on. Contiguous.
        purged: Training sessions dropped for overlapping the test window.
        embargoed: Training sessions dropped by the embargo buffer.
        fold: Zero-based index of this split.
    """

    train: tuple[date, ...]
    test: tuple[date, ...]
    purged: tuple[date, ...]
    embargoed: tuple[date, ...]
    fold: int

    def __post_init__(self) -> None:
        """Reject any split that could leak, however it was constructed."""
        if not self.train:
            raise SplitError(f"fold {self.fold} has no training sessions")
        if not self.test:
            raise SplitError(f"fold {self.fold} has no test sessions")
        overlap = set(self.train) & set(self.test)
        if overlap:
            raise SplitError(
                f"fold {self.fold}: {len(overlap)} session(s) appear in both train "
                f"and test, earliest {min(overlap)}. This is direct leakage."
            )
        if max(self.train) >= min(self.test):
            raise SplitError(
                f"fold {self.fold}: training runs to {max(self.train)}, at or after "
                f"the test fold begins on {min(self.test)}. Walk-forward means every "
                f"training session precedes every test session; a model fitted on the "
                f"future cannot be run in the present."
            )

    @property
    def dropped(self) -> int:
        """Total training sessions removed by purging and embargo."""
        return len(self.purged) + len(self.embargoed)

    def describe(self) -> str:
        """One line, carrying the cost of the split with it."""
        return (
            f"fold {self.fold}: train {self.train[0]}..{self.train[-1]} "
            f"({len(self.train)} sessions) | test {self.test[0]}..{self.test[-1]} "
            f"({len(self.test)}) | dropped {self.dropped} "
            f"({len(self.purged)} purged, {len(self.embargoed)} embargoed)"
        )


def sessions_between(sessions: list[date], start: date, end: date) -> list[date]:
    """Sessions in the inclusive range ``[start, end]``.

    Uses binary search on the sorted list rather than a scan, because this is
    called once per fold per candidate observation.
    """
    left = bisect_left(sessions, start)
    right = bisect_right(sessions, end)
    return sessions[left:right]


def purged_walk_forward(
    sessions: list[date],
    *,
    folds: int = 5,
    horizon: int,
    embargo: int | None = None,
    min_train: int | None = None,
) -> list[WalkForwardSplit]:
    """Split sessions into expanding-window folds, purged and embargoed.

    Each fold trains on everything before its test window, minus the sessions
    whose ``horizon`` outcome window reaches into that test window, minus an
    embargo buffer.

    The training window *expands* rather than sliding. A sliding window would
    discard the early history, and with roughly 2,800 sessions available there
    is not enough data to spend it that way. The consequence -- later folds
    train on more data than earlier ones -- is real and is why fold results
    should be reported individually, not averaged into one number.

    Args:
        sessions: Trading sessions. Sorted and de-duplicated internally.
        folds: Number of test windows. Each is the same length.
        horizon: Sessions an observation's outcome spans **forward** -- the
            holding period, or the label window. Not the feature lookback; see
            the module docstring for why confusing the two is the failure this
            module was written to avoid. Passing 0 disables purging entirely.
        embargo: Sessions to drop after each test window. Defaults to
            ``DEFAULT_EMBARGO_FRACTION`` of the sample, minimum 1.
        min_train: Minimum training sessions for a fold to be emitted. Defaults
            to ``horizon + 1``, which is a **validity** floor -- enough to form
            one complete observation -- and emphatically not a statistical
            adequacy floor. Callers testing a real hypothesis should set it far
            higher and say so in the trial register.

    Returns:
        Splits in chronological order.

    Raises:
        SplitError: if the inputs cannot produce a valid split. This is a
            refusal, not a warning: silently returning fewer folds than asked
            for would let a caller believe it had cross-validated when it had
            not.
    """
    ordered = sorted(set(sessions))
    total = len(ordered)

    if folds < 1:
        raise SplitError(f"folds must be at least 1, got {folds}")
    if horizon < 0:
        raise SplitError(f"horizon must not be negative, got {horizon}")
    if embargo is not None and embargo < 0:
        raise SplitError(f"embargo must not be negative, got {embargo}")

    gap = embargo if embargo is not None else max(1, int(total * DEFAULT_EMBARGO_FRACTION))
    floor = min_train if min_train is not None else horizon + 1
    floor = max(floor, 1)

    test_size = total // (folds + 1)
    if test_size < 1:
        raise SplitError(
            f"{total} sessions cannot be divided into {folds} test windows plus a "
            f"training set. Reduce folds, or supply more history."
        )

    # The binding constraint is fold 0, not the sample as a whole. In an
    # expanding window the first fold has the least history, and it must still
    # survive losing `horizon` sessions to purging and `gap` to the embargo.
    first_test_start = total - folds * test_size
    required = floor + horizon + gap
    if first_test_start < required:
        raise SplitError(
            f"{total} sessions is not enough for {folds} fold(s) with horizon "
            f"{horizon}: the first fold trains on only the {first_test_start} "
            f"sessions before its test window, and needs {required} of them "
            f"({floor} minimum + {horizon} purged + {gap} embargoed). Later folds "
            f"are fine -- in an expanding window the first is always the tight one. "
            f"Reduce folds, shorten the horizon, or supply more history."
        )

    splits: list[WalkForwardSplit] = []
    for fold in range(folds):
        test_start = total - (folds - fold) * test_size
        test_end = test_start + test_size
        if test_start < 1:
            raise SplitError(
                f"fold {fold} would begin at index {test_start}, leaving no training data before it"
            )

        test = ordered[test_start:test_end]
        candidates = ordered[:test_start]

        # Purge: drop any training session whose outcome extends into the test
        # period. An observation at index i resolves at i + horizon, so it is
        # contaminated exactly when i + horizon >= test_start.
        purge_from = max(0, test_start - horizon)
        purged = tuple(candidates[purge_from:])
        train = list(candidates[:purge_from])

        # Embargo: drop a further buffer immediately before the test window.
        # Applied after purging so the two are reported separately -- when a
        # fold's training set turns out to be surprisingly small, which of the
        # two caused it is the first thing worth knowing.
        embargoed: tuple[date, ...] = ()
        if gap and train:
            cut = max(0, len(train) - gap)
            embargoed = tuple(train[cut:])
            train = train[:cut]

        # Unreachable given the precheck above: fold 0 has the least history in
        # an expanding window, so if it survived, every later fold does. Kept as
        # a consistency check between the precheck's arithmetic and the loop's
        # -- if the two ever drift apart, this fires instead of silently
        # emitting a fold with a starved training set.
        if len(train) < floor:  # pragma: no cover - see comment
            raise SplitError(
                f"fold {fold} has {len(train)} training sessions after purging "
                f"{len(purged)} and embargoing {len(embargoed)}, below the minimum "
                f"of {floor}. Earlier folds are the tight ones in an expanding "
                f"window; reduce folds or shorten the horizon rather than lowering "
                f"min_train."
            )

        splits.append(
            WalkForwardSplit(
                train=tuple(train),
                test=tuple(test),
                purged=purged,
                embargoed=embargoed,
                fold=fold,
            )
        )
    return splits
