# Auth0 Setup Checklist for DeepView MCP

This checklist prepares an Auth0 tenant to protect the DeepView MCP API and enables server-to-server access via client credentials.

## Quick References

- API Identifier (audience): `https://your-api.example.com/deepview-mcp/mcp`
- Recommended scopes: `deepview:read`
- Issuer/Token URL examples:
  - Tenant default domain:  
    - Issuer: `https://<your-tenant>.auth0.com/` (region-specific domains like `...us.auth0.com` are also common)
    - Token URL: `https://<your-tenant>.auth0.com/oauth/token`
  - Custom domain:  
    - Issuer: `https://auth.example.com/`  
    - Token URL: `https://auth.example.com/oauth/token`

## 1) Decide Tenant and Domain

- __Choose production source of truth__: continue using the tenant default domain, or configure a custom domain on that tenant for production (recommended).
- __Record values you will use in the app__:
  - Issuer: `<your issuer>`
  - Token URL: `<issuer>/oauth/token`
  - Audience: `https://your-api.example.com/deepview-mcp/mcp`

## 2) Create and Configure the API

- Go to Auth0 → APIs → Create API
  - Name: DeepView MCP
  - Identifier: `https://your-api.example.com/deepview-mcp/mcp`
  - Signing Algorithm: RS256
- In API → Settings:
  - Enable __RBAC__.
  - Enable __Add Permissions in the Access Token__.
- In API → Permissions:
  - Add: `deepview:read`

## 3) Machine-to-Machine (M2M) Application

- Create (or reuse) an M2M Application for server-to-server access.
- Applications → Your M2M App → API Permissions:
  - Authorize the DeepView API and grant `deepview:read`.
- Applications → Your M2M App → Settings:
  - Note `Client ID` and `Client Secret` (store securely).

## 4) Custom Domain (Optional, Recommended)

- Auth0 → Branding → Custom Domains → Add Domain
  - Enter `auth.yourdomain.com`, add the CNAME record, complete verification.
  - Enable custom domain for the API and your M2M app.
- After verification, use the custom domain as your issuer and token URL.

## 5) Security Hardening

- Rotate signing keys automatically (Tenant Settings → Signing Keys).
- Set reasonable Access Token lifetime (e.g., 24h for M2M). Adjust per risk appetite.
- Enable Attack Protection: brute-force protection and suspicious IP throttling.
- Disable development keys for social connections (if any are enabled).

## 6) Local Project Configuration

Populate `.env` (or secrets store) with:

```text
OIDC_ISSUER=<your issuer>
AUTH0_TOKEN_URL=<issuer>/oauth/token
OIDC_AUDIENCE=https://your-api.example.com/deepview-mcp/mcp
OAUTH_REQUIRED_SCOPES=deepview:read
AUTH0_CLIENT_ID=<client id>
AUTH0_CLIENT_SECRET=<client secret>
```

Token helper script usage:

```bash
# Fetch token and print example API call
./check_token.sh

# Or export ACCESS_TOKEN in your shell (requires jq)
source ./check_token.sh
```

## 7) Verification

- OpenID configuration resolves:
  - GET `<issuer>/.well-known/openid-configuration`
  - JWKS exists: `.../jwks.json`
- Token claims confirm configuration:
  - `iss` equals the issuer/custom domain
  - `aud` equals your configured audience (e.g., `https://your-api.example.com/deepview-mcp/mcp`)
  - `scope` includes `deepview:read`
- Call the DeepView MCP endpoint:

```bash
curl -s -X POST "$OIDC_AUDIENCE" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

Expected: HTTP 200 and a list of tools.

## 8) Troubleshooting

- 401 Unauthorized
  - Issuer or audience mismatch; wrong token URL; invalid signature; JWKS not found.
- 403 Forbidden
  - Missing scope; ensure RBAC is enabled and app is granted `deepview:read`.
- invalid_grant / access_denied
  - Bad client credentials; application disabled; client not authorized for the API.
- CORS / Allowed URLs
  - Only relevant for browser flows; configure allowed origins/redirects if needed later.
