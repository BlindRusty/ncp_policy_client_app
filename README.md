# MCP Client

A **Model Context Protocol (MCP)** Client implementation governed by the **NANDA Control Protocol (NCP)**. This project demonstrates how to discover, verify, cache, and interact with AI-agent servers (MCPs) in a secure, reliable, and policy-driven manner.

---

## About the Code

- **enforce_nanda.py**: Main entrypoint.  
  - Initializes the `MCPClient`, enforces NCP policies via `PolicyManager`, connects to an MCP server over SSE, and enters an interactive concole based interface for user queries.  
  - Routes natural-language queries through an LLM (Anthropic Claude) and, when appropriate, invokes registered tools (`get_recipe`, `get_nutrition`, etc.). This example uses API Ninja for the examples.
  
- **nandaPolicy.py**: Policy engine.  
  - Loads `policy.json` to retrieve organizational rules (e.g., `verified`, `provider`, `relevance_score`, `uptime`).  
  - Discovers candidate MCP endpoints via the NANDA registry API, matches them against policy qualifiers, caches verified endpoints to `cached_mcp_servers.json`, and falls back to cache on registry failure.  

- **cached_mcp_servers.json**: Local cache of verified MCP endpoints, refreshed every 72 hours.

- **requirements.txt**: Lists all Python dependencies (e.g., `mcp`, `anthropic`, `python-dotenv`, etc.).

---

## About the MCP Server

The MCP Server is hosted at https://nutrition-mcp-server.axonvertex.xyz/

The MCP server is registered at NANDA Registry : https://ui.nanda-registry.com/servers/e191684b-b0c3-4920-aa4c-f56de6a20684


API Provider for nutrition and recipes : API - Ninjas - https://api-ninjas.com/

For testing, a Free API key is already provided from the MCP server. One can use it with limited information to check the functionality of the MCP server and client in the NCP driven environment. 
    

---

## About the Policy

Policies are declared in **policy.json**. Key fields:

- `registry_discovery_end_point`: URL for registry queries.  
- `cache_mcp_servers_policy` (boolean): Enable or disable local caching.  
- `qualifiers_metrics`: Array of objects `{ name, value, need }`:  
  - **name**: Metadata attribute (e.g., `verified`, `provider`).  
  - **value**: Threshold or list of acceptable values.  
  - **need**: `mandatory` or `optional`, dictating enforcement strictness.  
- `policy_tags`: Human-readable tags summarizing policy goals (e.g., `Trust`, `Secure`, `Verifiable`).  

The `PolicyManager` class reads these settings to:
1. Query the NANDA Registry for MCPs matching basic criteria.  
2. Filter results to enforce each qualifier metric.  
3. Cache passing endpoints locally for resilience.  
4. Fall back to cached entries when live discovery fails.  

---

## Setup & Usage

### Prerequisites

- Python 3.8+  
- An **Anthropic Claude** API key (set `ANTHROPIC_API_KEY` in `.env`).

### Installation

1. **Clone the repository**:

        git clone https://github.com/BlindRusty/ncp_policy_client_app.git
        
        cd mcp-client

2. **Create and activate a virtual environment**:
   
        python3 -m venv venv
        source venv/bin/activate    # Linux/macOS
        # or
        venv\Scripts\activate     # Windows


3. **Install dependencies**:
   
    
        pip install -r requirements.txt  

    
    [ uv  openai  ollama ] are mentioned for further enhancing this client to interact via llama and openAI models. 


4. **Configure environment variables**:
   
        nano .env

    
        # Edit .env:
        #   POLICY_ENFORCEMENT_STATUS=True
        #   ANTHROPIC_API_KEY=<your_claude_key>


### Running the Client

Launch the MCP Client to discover and connect to a verifiable MCP server:


        python enforce_nanda.py


Discovers an endpoint via NCP policy.  


On startup, you will see policy directory prints, trust-verification messages, and a list of available tools. Then enter your queries:


        Query: What is the nutritional value of banana?
        ...response with nutritional facts from tools for this mcp server...
        Query: bye


---

## License

Released under the [MIT License](LICENSE).
