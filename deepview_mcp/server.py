"""
DeepView MCP Server - A Model Context Protocol server implementation
for analyzing large codebases using Gemini 1.5 Pro.
"""

import os
import logging
import sys
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any

# Configure logging to stderr instead of file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Log to stderr instead of file
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get Gemini API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set")
    raise ValueError("GEMINI_API_KEY environment variable must be set")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Global variable to store the codebase content
codebase_content = ""

def load_codebase_from_file(file_path: str) -> str:
    """Load codebase from a single text file."""
    global codebase_content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Loaded codebase from {file_path}, size: {len(content)} characters")
        codebase_content = content
        return content
    except Exception as e:
        logger.error(f"Error loading codebase: {str(e)}")
        raise

def create_mcp_server(model_name="gemini-2.5-pro-exp-03-25"):
    """Create and configure the MCP server.
    
    Args:
        model_name: The Gemini model to use for queries (default: gemini-2.5-pro-exp-03-25)
    
    Returns:
        An MCP server instance
    """
    from mcp.server.fastmcp import FastMCP
    
    mcp_server = FastMCP("DeepView MCP")
    
    @mcp_server.tool()
    def deepview(question: str, codebase_file: str = None) -> Dict[str, Any]:
        """
        Ask a question about the codebase using Gemini 2.5 Pro.
        
        Args:
            question: The question to ask about the codebase
            codebase_file: Optional path to the codebase file. If provided, will load this file
                          instead of using the globally loaded codebase.
        
        Returns:
            Dictionary with the query result or error
        """
        global codebase_content
        
        # Load codebase from file if provided as parameter
        local_codebase = codebase_content
        if codebase_file:
            try:
                logger.info(f"Loading codebase from parameter: {codebase_file}")
                local_codebase = load_codebase_from_file(codebase_file)
            except Exception as e:
                logger.error(f"Failed to load codebase from parameter: {str(e)}")
                return {"error": f"Failed to load codebase file: {str(e)}"}
        
        # Check if we have a codebase to work with
        if not local_codebase:
            return {"error": "No codebase loaded. Please provide a codebase file."}
        
        # Create prompt for Gemini
        prompt = f"""You are a programming assistant analyzing code. Below is the content of a code repository.
Please answer the following question about the code:

QUESTION: {question}

CODE REPOSITORY:
```
{local_codebase}
```

Provide a clear, accurate response based solely on the provided code."""

        try:
            # Use Gemini to generate a response
            logger.info(f"Using Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            return {"result": response.text}
        except Exception as e:
            logger.error(f"Error querying {model_name}: {str(e)}")
            return {"error": f"Failed to query {model_name}: {str(e)}"}
    
    return mcp_server
