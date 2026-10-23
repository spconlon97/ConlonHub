---
name: verify
description: Verify a change in Conlon Hub Core by running the relevant unittest tests, then the full suite, and reporting results honestly. Use after implementing or fixing code, or before claiming work is done.
---

# Verify

Run from `Projects\Core`. Tests use the standard library `unittest` (no pytest).
Prefer the project venv interpreter (`.\.venv\Scripts\python.exe`) when it exists,
otherwise `python`.

1. **Narrowest tests first.** Run the test module(s) covering the changed code, e.g.
   `python -m unittest tests.test_auth -v`.
2. **Full suite.** If those pass, run `python -m unittest discover -s tests -v`.
3. **Failures.** Read the traceback and fix the cause; do not weaken or skip tests
   to make them pass. Re-run step 1 and 2 after a fix.
4. **Report** exactly what ran: commands, pass/fail/skip counts, warnings, and
   anything not verified (e.g. no test covers the change, UI not checked).
   Never say it works without having run it.
