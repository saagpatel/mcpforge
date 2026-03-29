# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | Yes       |
| < 0.2   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in mcpforge, please **do not** open a public GitHub issue.

Instead, report it by opening a **private** GitHub Security Advisory:

1. Go to <https://github.com/saagpatel/mcpforge/security/advisories/new>
2. Describe the vulnerability, steps to reproduce, and the potential impact
3. We will acknowledge the report within 72 hours and aim to release a patch within 14 days for confirmed issues

Please include as much detail as possible: affected versions, proof-of-concept code, and suggested mitigations if you have them.

## Scope

The following are in scope:

- Code execution vulnerabilities in the generator or CLI
- Prompt-injection risks in the LLM generation pipeline
- Dependency vulnerabilities with a known CVE that affect mcpforge at runtime

The following are **out of scope**:

- Vulnerabilities in generated server code (that is user-controlled output)
- Issues in transitive dependencies without a direct impact on mcpforge
