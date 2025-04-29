"""
Author : Krishnendu Dasgupta

"""

# --- Standard Library Imports ---
import asyncio            # Async IO for concurrency
import json               # Parse and serialize JSON
import os                 # Environment variables and filesystem operations
from typing import Optional  # Type hint for optional values
from contextlib import AsyncExitStack  # Manage multiple async context managers
import sys                 # Access command-line arguments

# --- Third-Party Imports ---
from mcp import ClientSession           # MCP client session for tool communication
from mcp.client.sse import sse_client   # SSE client for streaming MCP events
from anthropic import Anthropic         # Anthropic Claude LLM client
from dotenv import load_dotenv          # Load .env configurations
import requests                         # HTTP requests for registry discovery

# Local policy engine import
# from policy import get_verifiable_mcp_endpoint
from nandaPolicy import PolicyManager   # Implements NCP policy logic

# Load environment variables from a .env file into os.environ
load_dotenv()

# Global flag indicating whether policy enforcement is active
POLICY_ENFORCEMENT = os.getenv("POLICY_ENFORCEMENT_STATUS")


class MCPClient:
    """
    Main MCP client orchestrating policy enforcement, SSE connection,
    and LLM-based tool invocation. Preserves print statements for clarity.
    """

    def __init__(self):
        """
        Initialize internal state:
        - session: optional MCP ClientSession
        - exit_stack: manages async contexts
        - anthropic: Claude LLM client
        - session/streams contexts for cleanup
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self._session_context = None
        self._streams_context = None

    async def connect_to_sse_server(self, server_url: Optional[str]):
        """
        Connect to MCP server via SSE after policy evaluation.

        Steps:
        1. Enforce NCP policy to discover a valid endpoint.
        2. Append '/sse' to endpoint and validate scheme.
        3. Open SSE stream and initialize MCP ClientSession.
        4. List available tools and print them.
        """
        # 1. Fetch via policy
        policy = PolicyManager()
        endpoint = policy.get_verifiable_mcp_endpoint()
        # endpoint = get_verifiable_mcp_endpoint()  # legacy option

        if endpoint:
            # Construct SSE-endpoint URL
            server_url = endpoint.rstrip("/") + "/sse"
            print("  -----------------------------------------------------------------------------------------------------------")
            print("  Policies are enforced. Tools are fetched as per Policy. Response is curated as per verifiable trust source. Machine Intelligence will assist post veriable information is retrieved.")
            print("  -----------------------------------------------------------------------------------------------------------")
            print("  ====================TRUST VERIFICATION PROCESS ENDED AS PER POLICY==========================")
        else:
            # No valid endpoint; skip SSE
            print("  -----------------------------------------------------------------------------------------------------------")
            print("  Policies are enforced. Tools cannot be fetched as per Policy. The response is on trained data and previous learnings on the Machine Intelligence.")
            print("  -----------------------------------------------------------------------------------------------------------")
            print("  ====================TRUST VERIFICATION PROCESS ENDED AS PER POLICY==========================")
            return

        # 2. Ensure it's a valid HTTP/HTTPS URL
        if not server_url.lower().startswith(("http://", "https://")):
            print(f"Invalid MCP URL: {server_url!r}. Skipping tool connection.")
            return

        # 3. Now connect via SSE
        try:
            self._streams_context = sse_client(url=server_url)
            streams = await self._streams_context.__aenter__()
            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()
            await self.session.initialize()

            # List and print available tools
            resp = await self.session.list_tools()
            tools = [t.name for t in resp.tools]
            print("")
            print("  ===========================CONNECTION ESTABLISHED======================================")
            print("")
            print(f"  Established Connection with MCP Server. Tools available: {tools}")
            print("")
            print("  ===========================[------------------]======================================")
            print("")

        except Exception as e:
            # Handle connection errors and cleanup
            print(f"Failed to connect to MCP server at {server_url}: {e}")
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
            if self._streams_context:
                await self._streams_context.__aexit__(None, None, None)
            self.session = None

    async def cleanup(self):
        """
        Gracefully exit all async contexts to close SSE and client sessions.
        """
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def process_query(self, query: str) -> str:
        """
        Process a user query. If a session exists, route through LLM and tools;
        otherwise return direct LLM response.

        :param query: User-entered text.
        :return: Generated or tool-augmented response.
        """
        messages = [{"role": "user", "content": query}]

        # Fallback: use only LLM if no session
        if not self.session:
            resp = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
            )
            return resp.content[0].text

        # 1. Fetch list of tools
        list_resp = await self.session.list_tools()
        available_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
            for t in list_resp.tools
        ]

        # 2. Ask LLM which tool to use
        llm_resp = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )

        final_text = []

        # 3. Iterate LLM content chunks
        for content in llm_resp.content:
            if content.type == 'text':
                # Plain text reply
                final_text.append(str(content.text))
            elif content.type == 'tool_use':
                # LLM decided to invoke a tool
                tool_name = content.name
                tool_args = content.input

                # Log and append invocation message
                printable_args = json.dumps(tool_args) if not isinstance(tool_args, str) else tool_args
                final_text.append(f"[Calling tool {tool_name} with args {printable_args}]")

                # Invoke the tool
                result = await self.session.call_tool(tool_name, tool_args)
                raw = result.content

                # Normalize output to string
                if isinstance(raw, list):
                    texts = [getattr(part, "text", str(part)) for part in raw]
                    tool_output = "\n".join(texts)
                elif isinstance(raw, str):
                    tool_output = raw
                elif hasattr(raw, "text"):
                    tool_output = raw.text
                else:
                    tool_output = str(raw)

                # Special post-processing for recipes
                if tool_name == "get_recipe":
                    parts = tool_output.split("Instructions:")
                    header = parts[0].replace("Title:", "\n# ").strip()
                    body = parts[1] if len(parts) > 1 else ""
                    recipe_text = header + "\n\n## Instructions:\n" + body.strip()
                    final_text.append(recipe_text)
                else:
                    final_text.append(tool_output)

                # 4. Feed tool output back into LLM conversation
                if getattr(content, "text", None):
                    messages.append({"role": "assistant", "content": content.text})
                messages.append({"role": "user", "content": tool_output})

                # 5. Let LLM continue with updated history
                llm_resp = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=messages,
                )
                final_text.append(llm_resp.content[0].text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """
        Start interactive prompt. Users submit queries until typing 'bye'.
        """
        print('  Welcome to "KNOW YOUR FOOD Hub" ')
        print('  -------------------------------')
        print('  You can start your chat with your "Nutrition and Recipe Assistant"')
        print('  --------------------------------')
        print('  At any point type bye to exit.')
        print('  --------------------------------')
        print('  --------------CONVERSATION BEGINS-------------------')
        while True:
            query = input('  \nQuery: ').strip()
            if query.lower() in ['bye', 'good bye', 'goodbye', 'bye bye', 'byebye']:
                print('  Goodbye! Ending the conversation.')
                print('')
                print('  =================ALL CONNECTIONS CLOSED=============================')
                print('\n')
                break
            try:
                resp = await self.process_query(query)
                print('\n' + resp)
            except Exception as e:
                print(f"\nError: {e}")


async def main():
    """
    Entry point when script is run directly.
    Performs trust verification then starts SSE and chat loop.
    """
    server_url = sys.argv[1] if len(sys.argv) > 1 else None
    client = MCPClient()
    try:
        print('')
        print('  ====================TRUST VERIFICATION PROCESS INITIATED AS PER POLICY==========================')
        print('  Policies are getting enforced. Kindly wait till we validate verifiable mcp servers as per your policy : ')
        await client.connect_to_sse_server(server_url)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
