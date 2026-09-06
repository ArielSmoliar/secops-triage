# First authorized OpenAI attempt — 2026-09-06

The owner explicitly authorized one faulty-candidate attempt, at most eight model requests, capped at $3.50. The key was supplied through the local Git-ignored `.env`. The attempt ran at commit `10679fccd06ff508588861f227ecb1592a737413`.

## Outcome

- Run: `72905944fafb4333ad8569baff32d825`
- Session: `50cd871e27e84210bf62931aee45862a`
- Result: stopped with `model_failed`; run blocked.
- One provider dispatch reservation; zero tool calls; no assessment or readiness packet.
- No usage metadata returned. The $0.422308 reservation remains uncertain; the reported-estimate field of zero does **not** mean a confirmed zero charge.
- The grant is closed. No retry, candidate approval, or promotion occurred.

The local records remain in `data/openai-first-authorized-20260906/`: the SQLite store and immutable artifacts, redacted result/report, and a mode-0600 owner capability file inside a mode-0700 directory. The API key is not copied there. Both this directory and `.env` are Git-ignored. The committed `outputs/openai-first-attempt.json` is the redacted outcome only.

## Pre-dispatch review

Automatic approval review initially rejected execution because the outbound data had not been verified. No command or paid attempt ran on that rejection. An existing mocked-provider integration test then captured the seven-request synthetic path, including the complete tool definitions and unique messages. Inspection confirmed only fixed instructions, an eight-line regression template, generated IDs/hashes, routes, counts, timings, and HTTP status/field-name summaries. Owner tokens and credential canaries were absent. No candidate source bundle, customer document, unrelated file, or `.env` content appears in the body. The key authenticates to the explicitly selected `api.openai.com` service through the Authorization header.

The same bounded action was resubmitted with that evidence and allowed by automatic approval review. The separate payload audit made no external calls. It remains at `/private/tmp/migration-proof-egress-audit.json` for local inspection.

## Diagnosis and fix

A subsequent credential-free, HTTP-free TLS diagnostic found that this Python installation had no default CA file or CA directory and loaded zero CA certificates. Certificate verification against `api.openai.com` failed with verification code 20. This reproduces a connection failure independently of the model or key. The original transport deliberately retained only a generic failure, so no provider response or billing metadata is available for that attempt.

The transport now supplies the already locked `certifi==2026.7.22` bundle explicitly to `ssl.create_default_context`. Certifi is declared directly in the optional agent extra; no package version was changed and no new package was introduced. Hostname and certificate verification remain enabled. A regression test verifies that missing ambient CA paths do not prevent loading the pinned roots.

A TLS-only diagnostic after the fix loaded 121 CA certificates and completed TLS 1.3 verification against `api.openai.com`. It sent no HTTP request, API credential, or inference payload. This verifies connectivity, not API-key validity, account billing, model access, or real model behavior.

## Next action

The failed attempt is preserved and cannot be replayed. A replacement requires a new run, a new explicit owner grant, and owner authorization. A proposed replacement uses at most seven requests with a $3.00 ceiling: its maximum reservations are $2.956156, and together with the prior uncertain $0.422308 reservation total $3.378464, within the original $3.50 envelope. No replacement has been authorized or executed by this document.
