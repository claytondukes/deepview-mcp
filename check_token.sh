#!/bin/bash

# Replace tenant, client_id, client_secret, and the audience EXACTLY as registered

set -euo pipefail

# Allow overriding which env file to load (defaults to .env at repo root)
ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  # export all vars defined in the env file for this shell
  set -a
  . "$ENV_FILE"
  set +a
fi

# Prefer new standardized env vars; fall back to legacy placeholders if present
AUTH0_CLIENT_ID="${AUTH0_CLIENT_ID:-${YOUR_CLIENT_ID:-}}"
AUTH0_CLIENT_SECRET="${AUTH0_CLIENT_SECRET:-${YOUR_CLIENT_SECRET:-}}"
OIDC_ISSUER="${OIDC_ISSUER:-}"
OIDC_AUDIENCE="${OIDC_AUDIENCE:-}"
AUTH0_TOKEN_URL="${AUTH0_TOKEN_URL:-${OIDC_ISSUER%/}/oauth/token}"

# Validate required inputs
missing=()
[[ -z "${AUTH0_CLIENT_ID:-}" ]] && missing+=(AUTH0_CLIENT_ID)
[[ -z "${AUTH0_CLIENT_SECRET:-}" ]] && missing+=(AUTH0_CLIENT_SECRET)
[[ -z "${OIDC_AUDIENCE:-}" ]] && missing+=(OIDC_AUDIENCE)
if [[ -z "${AUTH0_TOKEN_URL:-}" ]]; then
  missing+=(AUTH0_TOKEN_URL_or_OIDC_ISSUER)
fi
if (( ${#missing[@]} > 0 )); then
  echo "Missing required env vars: ${missing[*]}" >&2
  echo "Hint: set them in $ENV_FILE (see .env.example) or export before running." >&2
  exit 1
fi

# Fetch token with a simple JSON payload. If jq is available, extract access_token; otherwise print full JSON.
if command -v jq >/dev/null 2>&1; then
  ACCESS_TOKEN=$(curl -s "${AUTH0_TOKEN_URL}" \
    -H 'content-type: application/json' \
    -d '{"client_id":"'"${AUTH0_CLIENT_ID}"'","client_secret":"'"${AUTH0_CLIENT_SECRET}"'","audience":"'"${OIDC_AUDIENCE}"'","grant_type":"client_credentials"}' \
    | jq -r .access_token)
else
  echo "Note: jq not found; printing full JSON response:" >&2
  curl -s "${AUTH0_TOKEN_URL}" \
    -H 'content-type: application/json' \
    -d '{"client_id":"'"${AUTH0_CLIENT_ID}"'","client_secret":"'"${AUTH0_CLIENT_SECRET}"'","audience":"'"${OIDC_AUDIENCE}"'","grant_type":"client_credentials"}'
  exit 0
fi

if [[ -z "${ACCESS_TOKEN}" || "${ACCESS_TOKEN}" == "null" ]]; then
  echo "Failed to obtain access token. Check client credentials, issuer, and audience." >&2
  exit 1
fi

export ACCESS_TOKEN
echo "Obtained ACCESS_TOKEN (exported in current shell if sourced)."
echo
echo "Example call:"
echo "  curl -s -X POST \"$OIDC_AUDIENCE\" \\
    -H 'Content-Type: application/json' \\
    -H \"Authorization: Bearer $ACCESS_TOKEN\" \\
    -d '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/list\"}'"

# Quick sanity: decode claims to verify iss and aud (optional)
if command -v python >/dev/null 2>&1; then
  if ! python - <<'PY'
try:
    import os, jwt
    t=os.environ.get("ACCESS_TOKEN")
    h=jwt.get_unverified_header(t)
    c=jwt.decode(t, options={"verify_signature": False})
    print("alg:", h.get("alg"))
    print("iss:", c.get("iss"))
    print("aud:", c.get("aud"))
    print("scope:", c.get("scope"))
except Exception:
    raise SystemExit(1)
PY
  then
    echo "Note: PyJWT not available; skipping token claims decode."
  fi
else
  echo "Note: Python not available; skipping token claims decode."
fi
