# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
private vulnerability reporting on this repository ("Security" tab →
"Report a vulnerability"), or email **admin@trugs.ai** if private reporting
is unavailable.

You can expect an acknowledgement within a few business days. Please include
a reproduction (the TRUG/TRL input and the command run) where possible.

## Supported versions

Only the **latest released version** of each package (`trugs-tools`,
`trugs-folder`) receives security fixes.

## Scope notes

These are local CLI tools operating on files you supply. They make no network
calls during normal operation and execute no code from the graphs they
process. Reports about malicious `.trug.json` / TRL inputs causing unexpected
code execution, path traversal outside the target directory, or resource
exhaustion are explicitly in scope.
