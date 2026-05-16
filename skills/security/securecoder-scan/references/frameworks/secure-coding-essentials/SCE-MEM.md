# Secure Coding Essentials — Memory Safety (SCE-MEM)

## Control objective

Memory-safety weaknesses — writing or reading outside allocated bounds, using memory after it is freed, dereferencing invalid pointers — are the highest-impact class of defect in memory-unsafe languages and remain reachable in memory-managed languages through FFI and `unsafe` code. They lead directly to crashes, information disclosure, and arbitrary code execution.

This chapter applies to any code that performs manual memory management, raw pointer arithmetic, fixed-size buffer manipulation, or foreign-function calls into memory-unsafe code.

## SCE-MEM controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-MEM-1** | Verify that every write into a buffer is bounds-checked against the destination's actual capacity before the write occurs. | CWE-787 |
| **SCE-MEM-2** | Verify that every read from a buffer stays within the allocated extent, including in loops and pointer walks over untrusted-length data. | CWE-125 |
| **SCE-MEM-3** | Verify that memory is never accessed after it has been freed, and that freed pointers are not retained or reused. | CWE-416 |
| **SCE-MEM-4** | Verify that each allocation is freed exactly once on every code path, with no double-free reachable via error handling. | CWE-415 |
| **SCE-MEM-5** | Verify that pointers are checked against null (and other invalid sentinels) before dereference, including return values of allocators and lookups. | CWE-476 |
| **SCE-MEM-6** | Verify that pointers or references to stack-allocated storage are not returned from a function or stored beyond the lifetime of their frame. | CWE-562 |
| **SCE-MEM-7** | Verify that buffer size arguments passed to copy, move, and format routines are derived from the destination capacity, never from the (untrusted) source length alone. | CWE-120 |

## Verdict guidance

For a memory-managed language file with no FFI or `unsafe` usage, most controls here are legitimately `N/A` — state that the runtime guarantees the property. For C / C++ / unsafe Rust / assembly, evaluate each control against the actual buffer and pointer operations in the file.
