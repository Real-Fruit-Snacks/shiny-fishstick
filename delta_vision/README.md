# My Textual App

A professional Textual-based Python application.

## Keywords file format

Provide a markdown file (e.g. `keywords.md`) to power highlighting and the Keywords screen.

Rules:
- Category headers start with `#`, e.g. `# Security (Red)` or `# Networking`.
- The color in parentheses is optional; when omitted, a default theme color is used.
- Lines starting with `#` that do not match a header (e.g. `# comment ...`) are treated as comments.
- Empty categories are allowed and retained.
- Inline comments after a keyword are stripped when preceded by whitespace: `foo  # note` -> `foo`.

Example:

```
# Security (Red)
malware
phishing  # social engineering

# Networking
TCP
UDP
```
