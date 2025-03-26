"""
Command-line interface for DeepView MCP.
"""

import sys
import argparse
import logging
from .server import load_codebase_from_file, create_mcp_server

logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="DeepView MCP - A Model Context Protocol server for analyzing large codebases")
    parser.add_argument("codebase_file", nargs="?", type=str, help="Path to the codebase file to load")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        default="INFO", help="Set the logging level")
    parser.add_argument("--model", type=str, default="gemini-2.5-pro-exp-03-25",
                        help="Gemini model to use (default: gemini-2.5-pro-exp-03-25)")
    return parser.parse_args()

def main():
    """Main entry point for the CLI."""
    args = parse_args()
    
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
        logger.warning("No codebase file provided. You'll need to provide one as a parameter to the deepview function.")
    
    # Create and run MCP server
    mcp_server = create_mcp_server(model_name=args.model)
    logger.info(f"Starting MCP server with model: {args.model}")
    mcp_server.run()

if __name__ == "__main__":
    main()
