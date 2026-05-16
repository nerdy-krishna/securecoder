# Secure Coding Essentials — Access Control & Privilege (SCE-ACCESS)

## Control objective

Code that performs privileged operations, enforces permissions, or runs with elevated rights must check authorization, hold privilege for the shortest possible time, and enforce decisions in the trusted component. Failures here turn any other bug into a privilege escalation. This chapter applies to code that gates access, manipulates permissions, or runs privileged.

## SCE-ACCESS controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-ACCESS-1** | Verify that every privileged or sensitive operation checks the caller's authorization before proceeding. | CWE-862 |
| **SCE-ACCESS-2** | Verify that elevated privileges are dropped as soon as they are no longer required, and not held for the lifetime of the process when avoidable. | CWE-250 |
| **SCE-ACCESS-3** | Verify that files and resources are created with least-privilege permissions and are not world-writable or world-readable when they hold sensitive data. | CWE-732 |
| **SCE-ACCESS-4** | Verify that authorization decisions are enforced in the trusted component and cannot be bypassed by a caller that skips or forges the client-side path. | CWE-602 |

## Verdict guidance

Determine whether the file performs any access-gating or privileged operation. A file with no privilege or permission logic can mark these `N/A`. For kernel, daemon, or setuid code, evaluate each control against the actual privilege transitions and permission checks.
