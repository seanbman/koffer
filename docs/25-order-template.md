# 25. Dreadnought Order Template

Use this template for every Cursor Project Arm implementation Order.

~~~markdown
# ORDER <phase>-<sequence>: <bounded outcome>

## Mission
One concrete deliverable.

## Authority
- Canonical source branch: dev
- Execution: Cursor Project Arm in Dreadnought scratch only
- Canonical promotion: Dreadnought after verification
- Host-direct implementation: prohibited

## Documentation
Read:
- docs/INSTRUCTIONS.md
- docs/AGENTS.md
- docs/<relevant architecture/domain docs>
- Screen IDs: <Sxx>
- Mockups: docs/mockups/<...>.svg

## In scope
- exact behaviors/files/modules

## Out of scope
- explicit neighboring work not to absorb

## Acceptance criteria
- observable/testable criteria copied or derived from canonical docs

## Safety invariants
- source file constraints
- metadata constraints
- concurrency constraints

## Expected tests
- exact test categories/commands

## Allowed files/modules
- paths

## Deliverables
- code
- tests
- migration/docs only when relevant
- evidence

## Arm completion response
STATUS:
SUMMARY:
FILES CHANGED:
TESTS ADDED:
TEST COMMANDS:
TEST RESULTS:
ACCEPTANCE EVIDENCE:
KNOWN REMAINING ROADMAP WORK:
TOKENS INPUT:
TOKENS OUTPUT:
TOKENS TOTAL:
~~~

## Dreadnought verification checklist

Before promotion:
- inspect diff;
- confirm no scope escape;
- rerun applicable tests;
- run safety regression subset if mutation-related;
- verify schema migration if persistence changed;
- verify UI acceptance if screen changed;
- verify no canonical host edit was mixed in;
- record Grapher/evaluation;
- record token telemetry.

## Failure handling

If Arm fails:
1. preserve evidence;
2. classify root cause;
3. revise Order or strategy;
4. refresh scratch from canonical if needed;
5. dispatch again.

After three materially similar failures, Dreadnought must change approach rather than resend equivalent instructions.
