"""
Command-line interface for DeepView MCP.
"""

import sys
import argparse
import logging
from .server import create_http_server, load_codebase_from_file

logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="DeepView MCP - A Model Context Protocol server for analyzing large codebases")
    parser.add_argument("codebase_file", nargs="?", type=str, help="Path to the codebase file to load")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        default="INFO", help="Set the logging level")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash",
                        help="Gemini model to use (default: gemini-2.5-flash)")
    parser.add_argument("--transport", type=str, choices=["stdio", "http"], default="stdio",
                        help="Transport method (default: stdio)")
    parser.add_argument("--host", type=str, default="localhost",
                        help="Host to bind to for HTTP transport (default: localhost)")
    parser.add_argument("--port", type=int, default=8019,
                        help="Port to bind to for HTTP transport (default: 8019)")
    return parser.parse_args()

def main():
    """Main entry point for the CLI."""
    import os
    
    args = parse_args()
    
    # Override args with environment variables if available
    args.transport = os.getenv("MCP_TRANSPORT", args.transport)
    args.host = os.getenv("MCP_HOST", args.host)
    args.port = int(os.getenv("MCP_PORT", str(args.port)))
    args.log_level = os.getenv("LOG_LEVEL", args.log_level)
    args.model = os.getenv("GEMINI_MODEL", args.model)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    
    # Load codebase if provided
    if args.codebase_file:
        try:
            load_codebase_from_file(args.codebase_file)
            logger.info(f"Loaded codebase from command line argument: {args.codebase_file}")
        except Exception as e:
            logger.error(f"Failed to load codebase from command line argument: {str(e)}")
            sys.exit(1)
    else:
        # Try to load from default codebase directory if it exists
        default_codebase = "/app/codebase"
        if os.path.exists(default_codebase):
            codebase_files = [f for f in os.listdir(default_codebase) if f.endswith(('.txt', '.md'))]
            if codebase_files:
                try:
                    codebase_path = os.path.join(default_codebase, codebase_files[0])
                    load_codebase_from_file(codebase_path)
                    logger.info(f"Loaded codebase from default directory: {codebase_path}")
                except Exception as e:
                    logger.warning(f"Failed to load codebase from default directory: {str(e)}")
        
        if not hasattr(load_codebase_from_file, '_loaded'):
            logger.warning("No codebase file provided. You'll need to provide one as a parameter to the deepview function.")
    
    # Create and run HTTP server (simplified approach following lzdocs pattern)
    logger.info(f"Starting DeepView MCP server with model: {args.model}")
    logger.info(f"Server will be available at http://{args.host}:{args.port}")
    logger.info(f"MCP protocol endpoint: http://{args.host}:{args.port}/deepview-mcp/mcp")
    logger.info("REST endpoints: /health, /{project_name}, /codebase/{project_name}")
    
    try:
        import uvicorn
        app = create_http_server(model_name=args.model, host=args.host, port=args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())
    except ImportError:
        logger.error("uvicorn not available for HTTP transport")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
