# P1 Reproduction Contract Authority R3

This package repairs only the authority contract for a future P1 reproduction.
It does not run a reproduction, a backtest, a strategy, or a database query.

## Authority split

- **Algorithm source authority:** `28940a2572c051c6ba8b2ab6a077f706e800477d:tools/quick_predict.py`
  at blob `bb2826b84a782aa6f68d472b30221fa2d1781a4b` remains the historical P1 implementation under
  evaluation for both four-bet and five-bet use.
- **Diagnostic control authority:** `e56ce9f196342e9d50edc9fd19c42f72c1fa2047:tools/quick_predict.py`
  at blob `7ee44fa584442419410d675b3ec3598c161ad2ec` supplies `biglotto_5bet_orthogonal` only as a
  mechanical equal-ticket comparator.
- **Environment authority:** merged Environment R3 at
  `e6037b06c3030bc1efc6538fc1a936bd763958b6:research/p1_reproduction_environment_authority_r3` is referenced without
  modification.
- **Result artifact:** future reproduction output is outside this task and is not
  present in this package.

## Closed interpretation

The historical source blob does not contain `biglotto_5bet_orthogonal`. The later
symbol is therefore an explicit diagnostic-control exception and never enters
the historical P1 algorithm-source closure. Four-bet comparison uses the first
four ordered diagnostic tickets; five-bet comparison uses all five.

The diagnostic callable closure is BIG_LOTTO 1–49, deterministic, and accepts
only a supplied historical draw prefix. Static AST verification finds no DB,
network, random, or filesystem dependency in the named callable closure. The
helper module contains unrelated module-level DB and backtest code; that code is
excluded, unapproved, and must not be executed by a future consumer.

## Research and production boundary

The comparator is `HISTORICAL_RESEARCH_ONLY / NOT_ESTABLISHED /
DIAGNOSTIC_ONLY`. It is not a validated alternative, production candidate,
ranking signal, promotion signal, or rejection authority. POWER_LOTTO
`MAX_NUM=38` substitution and using P1 as its own control are forbidden.
