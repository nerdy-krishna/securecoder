# Secure Coding Essentials — Resource Management (SCE-RES)

## Control objective

Resources — memory, file descriptors, sockets, locks, handles, threads — are finite. Leaks and unbounded consumption lead to denial of service; untrusted input that drives allocation or iteration is a denial-of-service vector. This chapter applies to all code that acquires and releases resources.

## SCE-RES controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-RES-1** | Verify that every acquired resource is released on all code paths, including early returns and error branches (RAII, `defer`, `finally`, or explicit cleanup). | CWE-404 |
| **SCE-RES-2** | Verify that allocations are bounded and cannot be driven to memory exhaustion by attacker-controlled size or count. | CWE-789 |
| **SCE-RES-3** | Verify that loops and recursion whose iteration count is influenced by untrusted input have an enforced upper limit. | CWE-834 |
| **SCE-RES-4** | Verify that temporary files and directories are created with secure permissions, unpredictable names, and are cleaned up. | CWE-377 |

## Verdict guidance

Match every acquire with a release across all paths. SCE-RES-2 and SCE-RES-3 specifically concern untrusted-input-driven consumption — if no input reaches the allocation/loop, mark `N/A` and say why.
