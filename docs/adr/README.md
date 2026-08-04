# Architecture Decision Records

An ADR records a decision that was expensive to make and would be expensive to
reverse, together with the alternatives considered and the consequences
accepted.

The value is not the decision. It is being able to answer, two years later,
*"why did we do it this way, and has the reason expired?"*

## Format

```
# NNNN. Short title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Deprecated | Superseded by NNNN

## Context
The forces at play. Facts, constraints and requirements.

## Decision
What was decided, stated actively.

## Alternatives considered
What else was on the table and why it was not chosen.

## Consequences
What becomes easier, what becomes harder, what is now accepted as a cost.

## Revisit when
The condition that should trigger reopening this decision.
```

## Conventions

- Numbered sequentially, never renumbered.
- Immutable once accepted. To change a decision, write a new ADR that
  supersedes it and update the old one's status.
- Written when the decision is made, not retrospectively.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-initial-technology-stack.md) | Initial technology stack | Accepted |
