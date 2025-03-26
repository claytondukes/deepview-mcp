import sys
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv

"""
DeepView MCP Test Script

This script demonstrates how to use the DeepView MCP client to query a codebase
using the Gemini model. It loads a codebase file and sends a question to the MCP server,
then displays the response from the model.

Usage:
    python test.py "Your question about the codebase here"
"""

# Load environment variables from .env file
load_dotenv()

# Check for required environment variables
if not os.environ.get("GEMINI_API_KEY"):
    print("Error: GEMINI_API_KEY environment variable not found.")
    print("Please add your Gemini API key to the .env file:")
    print("GEMINI_API_KEY=your_api_key_here")
    sys.exit(1)

# Hardcode the path to the codebase file
CODEBASE_FILE = "./repomix-output.xml"

async def async_main():
    # Get question from command line arguments
    question = "What does this codebase do?"  # default question
    if len(sys.argv) > 1:
        question = sys.argv[1]
      
    # Set up server parameters
    server_params = StdioServerParameters(
        command="deepview-mcp", # sys.executable,
        args=[CODEBASE_FILE],
        env=os.environ.copy()  # Pass current environment variables including GEMINI_API_KEY
    )
    
    # Create exit stack for resource management
    async with AsyncExitStack() as stack:
        print(f"Starting server with codebase: {CODEBASE_FILE}", file=sys.stderr)
        
        # Connect to server via stdio transport
        stdio_transport = await stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        
        # Create client session
        session = await stack.enter_async_context(ClientSession(stdio, write))
        
        # Initialize the session
        await session.initialize()
        
        # List available tools
        print("Listing available tools...", file=sys.stderr)
        try:
            list_tools_response = await session.list_tools()
            print("Available Tools:", [tool.name for tool in list_tools_response.tools], file=sys.stderr)
        except Exception as e:
            print(f"Error listing tools: {str(e)}", file=sys.stderr)
            return 1
        
        # Query the codebase
        print(f"Querying codebase with question: '{question}'", file=sys.stderr)
        try:
            # Call the query_codebase tool
            call_response = await session.call_tool(
                "deepview", 
                {"question": question}
            )
            
            # Print the result
            if call_response is not None:
                # Debug: print full response
                print("Raw Response:", call_response, file=sys.stderr)
                
                # Handle the response based on its structure
                if hasattr(call_response, 'content') and call_response.content:
                    # Extract text from TextContent objects
                    if isinstance(call_response.content, list):
                        for item in call_response.content:
                            if hasattr(item, 'text'):
                                print(item.text)
                    else:
                        print(call_response.content)
                else:
                    print("No content found in response")
            else:
                print("Error: No response received from server")
                
        except Exception as e:
            print(f"Error querying codebase: {str(e)}", file=sys.stderr)
            return 1
    
    return 0

def main():
    return asyncio.run(async_main())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test.py <question>")
        print("Example:")
        print("  python test.py \"What is the main purpose of this codebase?\"")
        sys.exit(1)
    
    sys.exit(main())
