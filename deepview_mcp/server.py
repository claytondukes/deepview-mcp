import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

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
    
    # Create FastAPI app
    app = FastAPI(title="DeepView MCP Server", description="Codebase analysis server with MCP support")
    
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
    # Support both GET and POST for MCP protocol
    @app.post("/deepview-mcp/mcp")
    @app.get("/deepview-mcp/mcp")
    async def mcp_endpoint(request: Request):
        """MCP protocol endpoint for Windsurf integration."""
        try:
            # Handle GET requests (return server info)
            if request.method == "GET":
                return JSONResponse({
                    "name": "deepview-mcp",
                    "version": "1.0.0",
                    "description": "DeepView MCP Server for codebase analysis",
                    "protocol": "mcp",
                    "capabilities": ["tools"]
                })
            
            # Handle POST requests (MCP protocol)
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")  # JSON-RPC requires matching response ID
            
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
        filename: Optional[str] = Query(None, description="Optional specific codebase filename")
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
        filename: Optional[str] = Query(None, description="Optional specific codebase filename")
    ):
        """Analyze a project via GET request with /codebase/ prefix."""
        return analyze_project_get(project_name, question, filename)
    
    # OAuth/OpenID endpoints that Windsurf looks for (return minimal responses)
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
