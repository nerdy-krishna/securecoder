# Secure Coding Essentials — Integer Handling (SCE-INT)

## Control objective

Integer overflow, underflow, signedness confusion, and truncation produce wrong values that are then trusted as sizes, indices, lengths, or loop bounds — frequently the root cause of a downstream memory-safety violation. This chapter applies to code using fixed-width integer types, and to code in any language that performs binary parsing, bit manipulation, or size arithmetic on untrusted values.

## SCE-INT controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-INT-1** | Verify that arithmetic producing sizes, lengths, or counts cannot overflow undetected; use checked arithmetic or validate operands against the type's range first. | CWE-190 |
| **SCE-INT-2** | Verify that subtractions used for sizes or indices cannot underflow below zero / wrap to a large unsigned value. | CWE-191 |
| **SCE-INT-3** | Verify that conversions between signed and unsigned types do not reinterpret negative values as large positive ones in a security-relevant path. | CWE-195 |
| **SCE-INT-4** | Verify that narrowing conversions do not discard bits that carry security-relevant magnitude (e.g. a 64-bit length truncated to 32 or 16 bits). | CWE-197 |
| **SCE-INT-5** | Verify that any externally-supplied value used as an allocation size, array index, or loop bound is range-validated before use. | CWE-1284 |

## Verdict guidance

In arbitrary-precision-integer languages (Python) overflow controls are often `N/A` — say so explicitly. Signedness, truncation, and validation controls still apply wherever binary data is parsed or values are passed across an FFI boundary.
