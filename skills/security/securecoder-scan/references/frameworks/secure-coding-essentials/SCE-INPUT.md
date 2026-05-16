# Secure Coding Essentials — Input Validation & Untrusted Data (SCE-INPUT)

## Control objective

Any value crossing a trust boundary — network packets, files, environment, CLI arguments, IPC messages, deserialized objects — is untrusted until validated. Missing or weak validation is the entry point for the majority of exploitable conditions. This chapter applies to all code that consumes external input.

## SCE-INPUT controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-INPUT-1** | Verify that all external input is validated for type, length, range, and format against an allow-list expectation before it is used. | CWE-20 |
| **SCE-INPUT-2** | Verify that the length of variable-length input is checked before it drives a copy, parse, or allocation. | CWE-130 |
| **SCE-INPUT-3** | Verify that untrusted data used to build a filesystem path is canonicalized and confined to an intended directory before access. | CWE-22 |
| **SCE-INPUT-4** | Verify that parsers of structured input (packets, file formats, serialized blobs) handle malformed, truncated, and adversarial input without crashing or misbehaving. | CWE-1284 |
| **SCE-INPUT-5** | Verify that deserialization of untrusted data cannot instantiate arbitrary types, invoke constructors with side effects, or execute code. | CWE-502 |

## Verdict guidance

Identify each point where data enters the file from outside its trust boundary. For a file with no external input (pure internal logic, constants), most controls are `N/A` — name the reason. A network-input routine should be evaluated against every control here.
