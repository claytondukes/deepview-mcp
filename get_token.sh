#!/bin/bash

# Replace tenant, client_id, client_secret, and the audience EXACTLY as registered

set -euo pipefail

# Usage and flags
DEBUG=false
for arg in "$@"; do
  case "$arg" in
    --debug|-d)
      DEBUG=true
      shift || true
      ;;
    -h|--help)
      cat >&2 <<'USAGE'
Usage: ./get_token.sh [--debug]

Description:
  Fetches an OAuth access token (Auth0 Client Credentials) and prints it.

Defaults:
  - Prints ONLY the raw access token to stdout.

Options:
  --debug, -d   Print helpful context, example curl, and decoded claims.
  -h, --help    Show this help and exit.
USAGE
      exit 0
      ;;
    *)
      ;;
  esac
done

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

# Fetch token response JSON
RESPONSE=$(curl -s "${AUTH0_TOKEN_URL}" \
  -H 'content-type: application/json' \
  -d '{"client_id":"'"${AUTH0_CLIENT_ID}"'","client_secret":"'"${AUTH0_CLIENT_SECRET}"'","audience":"'"${OIDC_AUDIENCE}"'","grant_type":"client_credentials"}')

# Extract access_token using jq if available, otherwise Python. Fail if neither available.
if command -v jq >/dev/null 2>&1; then
  ACCESS_TOKEN=$(printf '%s' "$RESPONSE" | jq -r '.access_token // empty')
elif command -v python >/dev/null 2>&1; then
  ACCESS_TOKEN=$(printf '%s' "$RESPONSE" | python -c 'import sys, json;\n\
try:\n\
    data=json.load(sys.stdin); print(data.get("access_token", ""))\n\
except Exception:\n\
    print("")')
else
  echo "Error: need either 'jq' or 'python' to extract access_token. Please install one of them." >&2
  exit 1
fi

if [[ -z "${ACCESS_TOKEN}" || "${ACCESS_TOKEN}" == "null" ]]; then
  echo "Failed to obtain access token. Check client credentials, issuer, and audience." >&2
  exit 1
fi

# Default behavior: print ONLY the token
if [ "$DEBUG" = false ]; then
  printf '%s\n' "$ACCESS_TOKEN"
  exit 0
fi

# Debug/verbose mode
echo "Obtained ACCESS_TOKEN. Printing token first (for easy copy/paste):"
echo
echo "$ACCESS_TOKEN"
echo
echo "Example call:"
echo "  curl -s -X POST \"$OIDC_AUDIENCE\" \\
    -H 'Content-Type: application/json' \\
    -H \"Authorization: Bearer $ACCESS_TOKEN\" \\
    -d '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/list\"}'"

# Quick sanity: decode claims to verify iss and aud (optional)
if command -v python >/dev/null 2>&1; then
  if ! ACCESS_TOKEN="$ACCESS_TOKEN" python - <<'PY'
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
