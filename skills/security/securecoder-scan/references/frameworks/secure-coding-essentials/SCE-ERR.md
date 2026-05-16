# Secure Coding Essentials — Error & Exception Handling (SCE-ERR)

## Control objective

Unchecked failures, swallowed exceptions, and resource leaks on error paths turn recoverable conditions into security incidents — and error paths are the least-tested code in any program. This chapter applies to all code that calls fallible operations (allocation, I/O, syscalls, library calls, network operations).

## SCE-ERR controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-ERR-1** | Verify that the return value or error result of every fallible call is checked before its result is used. | CWE-252 |
| **SCE-ERR-2** | Verify that every error path releases all resources acquired before the failure point. | CWE-460 |
| **SCE-ERR-3** | Verify that errors and exceptions are handled at a level that can act on them, and are never silently discarded. | CWE-390 |
| **SCE-ERR-4** | Verify that error output crossing a trust boundary does not leak internal state, file paths, stack traces, or secrets. | CWE-209 |
| **SCE-ERR-5** | Verify that on an unexpected error the code fails closed — denies the operation or aborts — rather than continuing in an undefined state. | CWE-636 |

## Verdict guidance

Walk every fallible call and confirm its failure is checked and handled. A pure-data file with no fallible operations can mark these `N/A`. Pay attention to cleanup correctness on the error branch — SCE-ERR-2 is the most commonly violated.
