import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Query, Request, Depends, Security
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to store codebase content
codebase_content = ""

def load_codebase_from_file(file_path: str, update_global: bool = True) -> str:
    """
    Load codebase content from a file.
    
    Args:
        file_path: Path to the codebase file
        update_global: Whether to update the global codebase_content variable
    
    Returns:
        The loaded codebase content as a string
    """
    global codebase_content
    
    try:
        # Try multiple possible paths
        possible_paths = [
            file_path,
            f"/app/{file_path}",
            f"./codebase/{file_path}",
            f"/app/codebase/{file_path}"
        ]
        
        content = ""
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Loading codebase from: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Loaded codebase from {path}, size: {len(content)} characters")
                break
        
        if not content:
            raise FileNotFoundError(f"Codebase file not found at any of these paths: {possible_paths}")
        
        if update_global:
            codebase_content = content
            
        return content
        
    except Exception as e:
        logger.error(f"Error loading codebase: {str(e)}")
        raise

def create_http_server(model_name: str = "gemini-2.5-flash", host: str = "0.0.0.0", port: int = 8019):
    """
    Create a simple HTTP server that handles both MCP protocol and REST endpoints.
    Following the lzdocs pattern for Windsurf integration.
    """
    
    # Load environment variables
    load_dotenv()
    
    # Get Gemini API key from environment variables
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY environment variable not set")
        raise ValueError("GEMINI_API_KEY environment variable must be set")
    
    # Configure Gemini API
    genai.configure(api_key=GEMINI_API_KEY)

    # OAuth/OIDC Configuration
    OAUTH_ENABLED = os.getenv("OAUTH_ENABLED", "false").lower() == "true"
    OIDC_ISSUER = os.getenv("OIDC_ISSUER")
    OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")
    OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL")
    OIDC_ALGS = [alg.strip() for alg in os.getenv("OIDC_ALGS", "RS256").split(",") if alg.strip()]
    REQUIRED_SCOPES_STATIC = {s.strip() for s in os.getenv("OAUTH_REQUIRED_SCOPES", "").split(",") if s.strip()}
    CLOCK_SKEW = int(os.getenv("OAUTH_CLOCK_SKEW_SECONDS", "60"))

    http_bearer = HTTPBearer(auto_error=False)
    jwks_client: Optional[PyJWKClient] = None

    if OAUTH_ENABLED:
        if not OIDC_ISSUER or not OIDC_AUDIENCE:
            raise ValueError("OIDC_ISSUER and OIDC_AUDIENCE must be set when OAUTH_ENABLED=true")
        # Normalize issuer to have trailing slash
        if not OIDC_ISSUER.endswith("/"):
            OIDC_ISSUER = OIDC_ISSUER + "/"
        # Discover JWKS URL if not explicitly provided
        if not OIDC_JWKS_URL:
            import httpx
            discovery_url = f"{OIDC_ISSUER}.well-known/openid-configuration"
            try:
                resp = httpx.get(discovery_url, timeout=5.0)
                resp.raise_for_status()
                OIDC_JWKS_URL = resp.json().get("jwks_uri")
                if not OIDC_JWKS_URL:
                    raise ValueError("jwks_uri not found in OIDC discovery document")
            except Exception as e:
                logger.error(f"Failed to get OIDC discovery from {discovery_url}: {e}")
                raise
        # Initialize JWKS client
        jwks_client = PyJWKClient(OIDC_JWKS_URL)
    
    # Create FastAPI app
    app = FastAPI(title="DeepView MCP Server", description="Codebase analysis server with MCP support")

    # Helper functions for OAuth
    def _decode_and_validate(token: str) -> Dict[str, Any]:
        assert jwks_client is not None
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=OIDC_ALGS,
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER,
            leeway=CLOCK_SKEW,
        )
        return claims

    def _token_scopes_set(claims: Dict[str, Any]) -> set:
        scopes = set()
        if "scope" in claims and isinstance(claims["scope"], str):
            scopes.update(claims["scope"].split())
        if "scopes" in claims and isinstance(claims["scopes"], list):
            scopes.update(claims["scopes"])
        return scopes

    def _has_required_scopes(token_scopes: set, project_name: Optional[str]) -> bool:
        # If static required scopes are configured, require all of them OR a per-project scope
        if REQUIRED_SCOPES_STATIC and REQUIRED_SCOPES_STATIC.issubset(token_scopes):
            return True
        if project_name:
            project_scope = f"deepview:project:{project_name}:read"
            if project_scope in token_scopes:
                return True
        # If no static scopes configured and no project context, accept any valid token
        return not REQUIRED_SCOPES_STATIC and not project_name

    def get_current_token_claims(credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer)) -> Dict[str, Any]:
        if not OAUTH_ENABLED:
            return {"sub": "anonymous"}
        if credentials is None or not credentials.scheme or not credentials.credentials:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Authorization scheme must be Bearer")
        try:
            return _decode_and_validate(credentials.credentials)
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    def require_project_scope(project_name: str, credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer)) -> Dict[str, Any]:
        claims = get_current_token_claims(credentials)
        if not OAUTH_ENABLED:
            return claims
        token_scopes = _token_scopes_set(claims)
        if not _has_required_scopes(token_scopes, project_name):
            raise HTTPException(status_code=403, detail="Insufficient scope for this project")
        return claims
    
    def find_codebase_file(project_path: str, filename: Optional[str] = None) -> str:
        """Find codebase file in project directory with fallback logic."""
        search_paths = [
            f"/app/codebase/{project_path}",
            f"./codebase/{project_path}",
            f"codebase/{project_path}"
        ]
        
        default_filenames = ["codebase.xml", "codebase.txt", "codebase.md", "codebase.json"]
        if filename:
            default_filenames.insert(0, filename)
        
        for search_path in search_paths:
            for fname in default_filenames:
                full_path = f"{search_path}/{fname}"
                if os.path.exists(full_path):
                    logger.info(f"Found codebase file: {full_path}")
                    return full_path
        
        raise FileNotFoundError(f"No codebase file found in project: {project_path}")
    
    def analyze_with_gemini(project_name: str, question: str, codebase_content: str) -> str:
        """Analyze codebase content with Gemini."""
        system_prompt = (
            "You are a diligent programming assistant analyzing code. Your task is to "
            "answer questions about the provided code repository accurately and in detail. "
            "Always include specific references to files, functions, and class names in your "
            "responses. At the end, list related files, functions, and classes that could be "
            "potentially relevant to the question, explaining their relevance."
        )

        user_prompt = f"""
Below is the content of a code repository for project '{project_name}'. 
Please answer the following question about the code:

<QUESTION>
{question}
</QUESTION>

<CODE_REPOSITORY>
```
{codebase_content}
```
</CODE_REPOSITORY>"""

        logger.info(f"Analyzing project {project_name} with model: {model_name}")
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
        response = model.generate_content(user_prompt)
        return response.text
    
    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint for Docker health checks."""
        return JSONResponse({
            "status": "healthy", 
            "service": "DeepView MCP", 
            "model": model_name
        })
    
    # MCP protocol endpoint (following lzdocs pattern)
    # GET is public (no auth) and returns server info for discovery.
    @app.get("/deepview-mcp/mcp")
    def mcp_info():
        return JSONResponse({
            "name": "deepview-mcp",
            "version": "1.0.0",
            "description": "DeepView MCP Server for codebase analysis",
            "protocol": "mcp",
            "capabilities": ["tools"]
        })

    # HEAD should be allowed for clients probing the endpoint
    @app.head("/deepview-mcp/mcp")
    def mcp_info_head():
        # Return the same headers as GET but with empty body
        return JSONResponse({}, headers={})

    # OPTIONS should announce allowed methods
    @app.options("/deepview-mcp/mcp")
    def mcp_options():
        return JSONResponse({}, status_code=204, headers={"Allow": "GET,POST,HEAD"})

    # POST handles MCP JSON-RPC and enforces OAuth when enabled.
    @app.post("/deepview-mcp/mcp")
    async def mcp_endpoint(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer)
    ):
        """MCP protocol endpoint for Windsurf/ChatGPT integration (JSON-RPC)."""
        try:
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")  # JSON-RPC requires matching response ID
            
            # Resolve claims based on OAuth setting
            if OAUTH_ENABLED:
                claims = get_current_token_claims(credentials)
            else:
                claims = {"sub": "anonymous"}
            
            # Standard MCP initialization methods
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "deepview-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
                return JSONResponse(response)
            
            elif method == "notifications/initialized":
                # Notifications don't need responses in JSON-RPC
                return JSONResponse({})
            
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "deepview",
                                "description": "Analyze codebase content with AI",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question": {"type": "string", "description": "Question about the codebase"},
                                        "codebase_file": {"type": "string", "description": "Optional codebase file path"}
                                    },
                                    "required": ["question"]
                                }
                            },
                            {
                                "name": "list_codebase_files", 
                                "description": "List available codebase files",
                                "inputSchema": {"type": "object", "properties": {}}
                            }
                        ]
                    }
                }
                return JSONResponse(response)
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "deepview":
                    question = arguments.get("question")
                    codebase_file = arguments.get("codebase_file")
                    
                    if not question:
                        return JSONResponse({"error": "Question is required"}, status_code=400)
                    
                    try:
                        # Load codebase content
                        if codebase_file:
                            local_codebase = load_codebase_from_file(codebase_file, update_global=False)
                            project_name = os.path.basename(os.path.dirname(codebase_file))
                        else:
                            global codebase_content
                            local_codebase = codebase_content
                            project_name = "default"

                        if not local_codebase:
                            return JSONResponse({"error": "No codebase content available"}, status_code=404)

                        # Enforce per-project scope when OAuth is enabled
                        if OAUTH_ENABLED:
                            token_scopes = _token_scopes_set(claims)
                            if not _has_required_scopes(token_scopes, project_name):
                                return JSONResponse({"error": "Insufficient scope for this project"}, status_code=403)
                        
                        # Analyze with Gemini
                        answer = analyze_with_gemini(project_name, question, local_codebase)
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": answer
                                    }
                                ]
                            }
                        }
                        return JSONResponse(response)
                        
                    except Exception as e:
                        logger.error(f"Error in deepview tool: {str(e)}")
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32603,
                                "message": "Internal error",
                                "data": str(e)
                            }
                        }
                        return JSONResponse(error_response, status_code=500)
                
                elif tool_name == "list_codebase_files":
                    try:
                        files = []
                        codebase_dir = "/app/codebase" if os.path.exists("/app/codebase") else "codebase"
                        
                        if os.path.exists(codebase_dir):
                            for root, dirs, file_list in os.walk(codebase_dir):
                                for file in file_list:
                                    if file.endswith(('.xml', '.txt', '.md', '.json')):
                                        rel_path = os.path.relpath(os.path.join(root, file), codebase_dir)
                                        files.append(rel_path)
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text", 
                                        "text": f"Available codebase files:\n" + "\n".join(files) if files else "No codebase files found"
                                    }
                                ]
                            }
                        }
                        return JSONResponse(response)
                        
                    except Exception as e:
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32603,
                                "message": "Internal error",
                                "data": str(e)
                            }
                        }
                        return JSONResponse(error_response, status_code=500)
            
            # Unknown method error
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": f"Unknown method: {method}"
                }
            }
            return JSONResponse(error_response, status_code=400)
            
        except Exception as e:
            logger.error(f"MCP endpoint error: {str(e)}")
            return JSONResponse({"error": str(e)}, status_code=500)
    
    # REST endpoints for direct HTTP access
    @app.get("/{project_name}")
    def analyze_project_get(
        project_name: str,
        question: str = Query(..., description="Question to ask about the codebase"),
        filename: Optional[str] = Query(None, description="Optional specific codebase filename"),
        claims: Dict[str, Any] = Depends(require_project_scope)
    ):
        """Analyze a project via GET request with URL path."""
        try:
            codebase_file = find_codebase_file(project_name, filename)
            local_codebase = load_codebase_from_file(codebase_file, update_global=False)
            
            if not local_codebase:
                raise HTTPException(status_code=404, detail="No codebase content found")
            
            # Analyze with Gemini
            answer = analyze_with_gemini(project_name, question, local_codebase)
            
            return JSONResponse({
                "project": project_name,
                "codebase_file": codebase_file,
                "question": question,
                "answer": answer,
                "model": model_name
            })
            
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error analyzing project {project_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    @app.get("/codebase/{project_name}")
    def analyze_codebase_project_get(
        project_name: str,
        question: str = Query(..., description="Question to ask about the codebase"),
        filename: Optional[str] = Query(None, description="Optional specific codebase filename"),
        claims: Dict[str, Any] = Depends(require_project_scope)
    ):
        """Analyze a project via GET request with /codebase/ prefix."""
        return analyze_project_get(project_name, question, filename)
    
    # OAuth/OpenID endpoints that Windsurf looks for (return minimal responses)
    @app.get("/.well-known/mcp.json")
    def mcp_discovery(request: Request):
        """Discovery document for ChatGPT MCP custom connector.

        Served at /.well-known/mcp.json and should be routed to this backend
        (not to Auth0). NPM must special-case this single path.
        """
        # Derive Auth endpoints from issuer
        authz = None
        if OIDC_ISSUER:
            issuer = OIDC_ISSUER if OIDC_ISSUER.endswith("/") else f"{OIDC_ISSUER}/"
            authz = {
                "type": "oauth2",
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}authorize",
                "token_endpoint": f"{issuer}oauth/token",
                "audience": OIDC_AUDIENCE,
                "scopes": sorted(list(REQUIRED_SCOPES_STATIC)) if REQUIRED_SCOPES_STATIC else []
            }

        # Build absolute endpoint URL from proxy-aware headers
        xf_proto = request.headers.get("x-forwarded-proto")
        xf_host = request.headers.get("x-forwarded-host")
        scheme = xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme
        host = xf_host.split(",")[0].strip() if xf_host else request.headers.get("host", request.url.hostname)
        base = f"{scheme}://{host}"
        doc = {
            "name": "deepview-mcp",
            "version": "1.0.0",
            "description": "DeepView MCP Server for codebase analysis",
            "endpoint": f"{base}/deepview-mcp/mcp",
            "capabilities": ["tools"],
            "authorization": authz,
        }
        return JSONResponse(doc)

    # HEAD for discovery document
    @app.head("/.well-known/mcp.json")
    def mcp_discovery_head():
        return JSONResponse({}, headers={})

    # OPTIONS for discovery document
    @app.options("/.well-known/mcp.json")
    def mcp_discovery_options():
        return JSONResponse({}, status_code=204, headers={"Allow": "GET,HEAD"})

    # Root GET to avoid noisy 404s (returns same info as mcp_info)
    @app.get("/")
    def root_info():
        return JSONResponse({
            "name": "deepview-mcp",
            "version": "1.0.0",
            "description": "DeepView MCP Server for codebase analysis",
            "protocol": "mcp",
            "capabilities": ["tools"]
        })

    @app.get("/.well-known/oauth-protected-resource")
    def oauth_protected_resource():
        return JSONResponse({"error": "not_supported"}, status_code=404)
    
    @app.get("/.well-known/openid-configuration")
    def openid_configuration():
        return JSONResponse({"error": "not_supported"}, status_code=404)
    
    @app.get("/.well-known/oauth-authorization-server")
    def oauth_authorization_server():
        return JSONResponse({"error": "not_supported"}, status_code=404)
    
    @app.post("/register")
    def register_client():
        return JSONResponse({"error": "registration_not_supported"}, status_code=405)
    
    return app
