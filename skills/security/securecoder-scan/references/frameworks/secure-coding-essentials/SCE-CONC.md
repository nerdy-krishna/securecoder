# Secure Coding Essentials — Concurrency & Races (SCE-CONC)

## Control objective

Concurrent access to shared state without correct synchronization produces races — including time-of-check-to-time-of-use windows that defeat security checks, data corruption, and deadlock. This chapter applies to any code that runs in a multi-threaded, multi-process, interrupt, or async context, or that touches state shared across such contexts.

## SCE-CONC controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-CONC-1** | Verify that shared mutable state is accessed only under appropriate synchronization (lock, atomic, channel, or equivalent). | CWE-362 |
| **SCE-CONC-2** | Verify that there is no exploitable gap between checking a resource's state and acting on it (no TOCTOU). | CWE-367 |
| **SCE-CONC-3** | Verify that locks are acquired in a consistent global order so deadlock cannot occur. | CWE-833 |
| **SCE-CONC-4** | Verify that signal handlers and interrupt contexts call only async-signal-safe functions and touch only state that is safe to touch in that context. | CWE-364 |

## Verdict guidance

Determine whether the file's code runs concurrently or touches shared state. A single-threaded, no-shared-state file can mark all four `N/A`. For kernel, driver, or server code, evaluate each control against the actual locking discipline.
