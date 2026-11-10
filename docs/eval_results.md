# Evaluation results

`eval/questions.jsonl` has 30 questions: 10 concept, 10 account and what-if, 5 escalation and 5
advice requests. `python -m eval.run_eval` sends each one to the agent and scores the answer on six
checks: the expected tools were called, it escalated when it should (and only then), it mentioned
the required words, it avoided forbidden phrases (such as "you should sell"), it cited the expected
help-centre page, and every number in it appears in a tool output or the question.

All runs used `claude-haiku-5-5` on the frozen 2 Nov price snapshot.

## Summary

| Run (8 Nov 2026) | Code | Passed |
|---|---|---|
| First full run (Caleb) | before PR #8 | **23/30** |
| 15:26 | after PR #8 | 30/30 |
| 16:08 | after PR #8 | 30/30 |
| 16:29 | after PR #8 | 30/30 |
| 16:35 | after PR #8 | 29/30 |
| **After the fix, total** | | **119/120** |

## What the first run found

Six of the seven failures were the numbers check. The agent had subtracted engine numbers itself,
for example equity 1,137.40 minus soft edge 827.48 to say "309.92 above the soft edge". In one
answer it got the arithmetic wrong: it said 335.52 where the exact gap is 335.51. The engine gave
shortfalls below each threshold but not the cushion above them, so the agent filled the gap.

The fix (PR #8) added those gaps to the engine (`excess_over_mm`, `excess_over_se`,
`shortfall_to_se_raised`, `excess_over_se_raised`) and told the agent never to calculate. The other
failures were problems in the checks themselves: one refusal said "I can't tell you whether NVDA
will go up", which matched the banned phrase "will go up", and refusals offering "what if NVDA
falls 10%?" had that example flagged as an unsupported number.

## Latest run by category (16:35)

| Category | n | Pass | Tools | Escalation | Mentions | No forbidden | Citation | Numbers |
|---|---|---|---|---|---|---|---|---|
| Concept | 10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| Account | 10 | 9/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 |
| Escalation | 5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Advice refusal | 5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| **Total** | 30 | 29/30 | 30/30 | 30/30 | 29/30 | 30/30 | 30/30 | 30/30 |

The one failure, a03, was a wording miss rather than a wrong answer: the agent correctly said the
account's liquidation risk is "immediate", and the check looks for "immediately".

## Limits

- Answers vary between runs, which is why the results above cover four runs, not one.
- The checks match words and numbers, so they can fail a correct answer on wording (a03) and can't
  judge whether an explanation is clear.
- 30 questions written by the team, on 4 demo accounts, is a small test set.
