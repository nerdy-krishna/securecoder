# Secure Coding Essentials — Cryptography & Secrets (SCE-CRYPTO)

## Control objective

Weak algorithms, predictable randomness, reused nonces, and mishandled secrets undermine confidentiality and integrity regardless of how correct the surrounding code is. This chapter applies to any code that performs cryptographic operations or handles keys, passwords, tokens, or other secrets.

## SCE-CRYPTO controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-CRYPTO-1** | Verify that only current, non-deprecated cryptographic algorithms and modes are used (no MD5/SHA-1 for security, no DES/RC4, no ECB). | CWE-327 |
| **SCE-CRYPTO-2** | Verify that passwords are stored using a salted, memory-hard hash (argon2, scrypt, or bcrypt), never a plain or fast hash. | CWE-916 |
| **SCE-CRYPTO-3** | Verify that security-sensitive random values (keys, IVs, tokens, salts) come from a cryptographically secure RNG, not a general-purpose PRNG. | CWE-338 |
| **SCE-CRYPTO-4** | Verify that secrets — keys, tokens, passwords, connection strings — are not hardcoded in source. | CWE-798 |
| **SCE-CRYPTO-5** | Verify that secrets are never written to logs, error messages, telemetry, or other observable output. | CWE-532 |
| **SCE-CRYPTO-6** | Verify that IVs and nonces are never reused under the same key. | CWE-323 |

## Verdict guidance

A file with no cryptographic operations and no secret handling can mark these `N/A`. Where crypto is present, name the specific algorithm/mode/RNG observed when assigning a verdict.
