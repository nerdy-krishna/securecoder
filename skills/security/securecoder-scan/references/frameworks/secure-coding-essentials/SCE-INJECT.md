# Secure Coding Essentials — Injection Prevention (SCE-INJECT)

## Control objective

Injection occurs when untrusted data is interpreted as code or commands by some downstream interpreter — a shell, a SQL engine, an `eval`, a format-string processor, an HTML renderer. The defense is to keep data and code separate at the interface. This chapter applies to any code that constructs commands, queries, or markup, or that emits data into an interpreter.

## SCE-INJECT controls

| # | Description | CWE |
| :---: | :--- | :---: |
| **SCE-INJECT-1** | Verify that OS commands are invoked with an argument vector, never by concatenating untrusted input into a shell string. | CWE-78 |
| **SCE-INJECT-2** | Verify that database queries use parameterized statements or a query builder, never string concatenation with untrusted input. | CWE-89 |
| **SCE-INJECT-3** | Verify that the program does not evaluate, compile, or execute code constructed from untrusted input. | CWE-94 |
| **SCE-INJECT-4** | Verify that format strings are program-controlled constants, never derived from untrusted input. | CWE-134 |
| **SCE-INJECT-5** | Verify that data emitted into any interpreter (HTML, SQL, shell, LDAP, XML, regex) is encoded or escaped for that specific context, as close to the sink as possible. | CWE-79 |

## Verdict guidance

For each control, locate the sink (the interpreter) and trace whether untrusted data reaches it without separation. A file with no command, query, or markup construction can mark these `N/A` with that reason.
