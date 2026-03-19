# Turbopuffer Backend for LAML

Use Turbopuffer as the LAML backend for:
- long-term memories
- session contexts
- working memory items

## 1) Configure `.env`

```bash
LAML_VECTOR_BACKEND=turbopuffer
TURBOPUFFER_API_KEY=...
TURBOPUFFER_REGION=gcp-us-central1
TURBOPUFFER_BASE_URL=https://gcp-us-central1.turbopuffer.com
TURBOPUFFER_LONG_TERM_NAMESPACE=laml_long_term_memories
TURBOPUFFER_SESSIONS_NAMESPACE=laml_sessions
TURBOPUFFER_WORKING_MEMORY_NAMESPACE=laml_working_memory
TURBOPUFFER_EMBEDDING_DIMENSIONS=768
```

## 2) Existing deployments (optional rollout)

For existing Firebolt deployments, use a phased rollout with dual-write first, then flip reads after validation.

## 3) Safe cutover (recommended)

1. Keep reads on Firebolt:
   ```bash
   LAML_VECTOR_BACKEND=firebolt
   LAML_DUAL_WRITE_BACKEND=turbopuffer
   ```
2. Run parity checks while the system is live.
3. Flip reads:
   ```bash
   LAML_VECTOR_BACKEND=turbopuffer
   LAML_DUAL_WRITE_BACKEND=firebolt
   ```
4. After confidence window, remove dual-write:
   ```bash
   LAML_DUAL_WRITE_BACKEND=
   ```

## 4) Rollback

If issues appear after cutover:

```bash
LAML_VECTOR_BACKEND=firebolt
LAML_DUAL_WRITE_BACKEND=turbopuffer
```

This restores reads to Firebolt while preserving mirrored writes into Turbopuffer.

## 5) Notes

- Turbopuffer cloud storage/index observability is best viewed in the Turbopuffer dashboard: https://turbopuffer.com/dashboard/
- `TURBOPUFFER_EMBEDDING_DIMENSIONS` should match your embedding model output.
- API references:
  - https://turbopuffer.com/docs/quickstart
  - https://turbopuffer.com/docs/auth
  - https://turbopuffer.com/docs/write
  - https://turbopuffer.com/docs/query
