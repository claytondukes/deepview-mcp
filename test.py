import sys
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check for required environment variables
if not os.environ.get("GEMINI_API_KEY"):
    print("Error: GEMINI_API_KEY environment variable not found.")
    print("Please add your Gemini API key to the .env file:")
    print("GEMINI_API_KEY=your_api_key_here")
    sys.exit(1)

# Hardcode the path to the codebase file
CODEBASE_FILE = "/Users/xo/cloudfix-rightspend/repomix-output.xml"

async def async_main():
    # Get question from command line arguments
    question = "What does this codebase do?"  # default question
    if len(sys.argv) > 1:
        question = sys.argv[1]
    
    # Path to the server script
    server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    
    # Set up server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script, CODEBASE_FILE],
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
                "query_codebase", 
                {"question": question}
            )
            
            # Print the result
            if call_response is not None:
                # Debug: print full response
                print("Raw Response:", call_response, file=sys.stderr)
                
                if hasattr(call_response, 'result'):
                    print(call_response.result)
                else:
                    try:
                        # Try to access as dictionary
                        result = call_response.get('result')
                        if result:
                            print(result)
                        else:
                            print(f"Error: {json.dumps(call_response)}")
                    except Exception as e:
                        print(f"Error: Unable to extract result from response: {call_response}, {str(e)}")
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
