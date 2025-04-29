"""
Author : Krishnendu Dasgupta 
"""

# --- Standard Library Imports ---
import os               # Filesystem operations and environment variables
import json             # JSON serialization and deserialization
import requests         # HTTP requests for registry discovery
from datetime import datetime, timedelta  # Date calculations for cache expiry
from dotenv import load_dotenv            # Load environment variables from .env

# Load environment variables into os.environ
load_dotenv()


class PolicyManager:
    """
    Manages NCP policy enforcement: discovery, matching, caching, and endpoint resolution.
    """
    # Local cache filename for verified MCP servers
    CACHE_FILE = "cached_mcp_servers.json"

    def __init__(self, policy_path: str = "policy.json"):
        """
        Initialize PolicyManager:
        1) Load policies from JSON file
        2) Display protocol directory & guidelines
        3) Perform live discovery against NANDA Registry
        4) Display raw protocol response
        """
        # Path to policy JSON
        self.policy_path = policy_path
        # Load policy definitions into dict
        self.policies = self._load_json(policy_path)

        # 1) Show protocol directory & policy guidelines
        self._show_protocol_directory()

        # 2) Do a live discovery against registry
        self.registry_response_data, self.policy_metrics = self._discover_registry()

        # 3) Print the raw protocol response
        self._show_protocol_response()

    def _load_json(self, path: str) -> dict:
        """
        Helper to load and parse a JSON file.

        :param path: Path to JSON file.
        :return: Parsed JSON as dict.
        """
        with open(path, 'r') as f:
            return json.load(f)

    def _save_json(self, path: str, data: dict):
        """
        Helper to write a dict to a JSON file with indentation.

        :param path: Path to output JSON file.
        :param data: Dictionary to serialize.
        """
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)

    def get_url_response(self, url: str) -> str:
        """
        Perform HTTP GET and return text or error string.

        :param url: URL to fetch.
        :return: Response text or error message.
        """
        try:
            r = requests.get(url)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as e:
            return f"Error fetching the URL: {e}"

    def build_url(self, base: str, criteria: dict) -> str:
        """
        Construct a discovery URL by appending query parameters.

        :param base: Base endpoint (may include '?').
        :param criteria: Dictionary of query parameters.
        :return: Full URL string.
        """
        # Ensure single '?' and join criteria with '&'
        url = base.rstrip("?") + "?" + "&".join(f"{k}={v}" for k, v in criteria.items())
        return url

    def _discover_registry(self):
        """
        Discover MCP servers via NANDA registry based on default criteria.

        :return: Tuple of (registry response dict, policy metrics list).
        """
        # Default discovery filters
        criteria = {
            "limit": 3,
            "q": "recipe",
            "tags": "nutrition",
            "type": "tool",
            "verified": "true"
        }
        # Build URL and fetch response
        mcp_server_link = self.build_url(self.policies['registry_discovery_end_point'], criteria)
        response = self.get_url_response(mcp_server_link)
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            data = {}
        # Return raw data and qualifiers metrics for policy matching
        return data, self.policies['qualifiers_metrics']

    def _show_protocol_directory(self):
        """
        Print the protocol directory and policy guidelines to console.
        Preserves original formatting and print statements.
        """
        p = self.policies
        print(" ")
        print("  This Example is only for demonstration purpose")
        print("  This chat is controlled by AXONVERTEX AI Policy Control Group ")
        print("")
        print("  ====================PROTOCOL DIRECTORY ==========================")
        print("  ----------------------------------------------------------")
        print("  Protocol Cluster:", p['protocol_cluster'])
        print("  ----------------------------------------------------------")
        print("  Protocol Level:", p['protocol_level'])
        print("  ----------------------------------------------------------")
        print("  Policy Cluster:", p['policy_cluster'])
        print("  ----------------------------------------------------------")
        print("  MCP Registry URL:", p['mcp_registry'])
        print("  ----------------------------------------------------------")
        print("  Registry Discovery Endpoint:", p['registry_discovery_end_point'])
        print("  ----------------------------------------------------------")        
        print("  Policy for caching MCP Servers once verified :", p['cache_mcp_servers_policy'])
        print("  ----------------------------------------------------------")
        print("  Policy Tags for AXONVERTEX :", ", ".join(p['policy_tags']))
        print("  ----------------------------------------------------------")
        print("  ====================PROTOCOL DIRECTORY ==========================")
        print("")
        print("  ====================PROTOCOL POLICY GUIDELINES ==========================")
        for metric in p['qualifiers_metrics']:
            print(f"  Policy Enforced on Attribute Name : {metric['name']}, "
                  f"Attribute Acceptable Value: {metric['value']}, "
                  f"Attribute Need : {metric['need']}")
            print("  ------------------------------------------------------------------------------------------------------------------------")
        print("  ====================PROTOCOL POLICY GUIDELINES ==========================")
        print("")

    def _show_protocol_response(self):
        """
        Print the raw protocol response retrieved from the registry.
        """
        # Reuse default criteria for display consistency
        criteria = {
            "limit": 3,
            "q": "recipe",
            "tags": "nutrition",
            "type": "tool",
            "verified": "true"
        }
        url = self.build_url(self.policies['registry_discovery_end_point'], criteria)
        raw = self.get_url_response(url)
        print("  ==================== PROTOCOL RESPONSE START ==========================")
        print("")
        print("Response from URL:", raw)
        print("")
        print("  ==================== PROTOCOL RESPONSE END ==========================")

    def match_policy_and_get_url(self) -> dict | None:
        """
        Scan registry response data and return the first entry that matches all policy metrics.

        :return: Valid MCP server item dict or None.
        """
        # Create lookup for policy values by name
        vp = {m['name']: m for m in self.policy_metrics}
        # Iterate over discovered items
        for item in self.registry_response_data.get('data', []):
            if (
                item['verified'] == vp['verified']['value'] and
                item['provider'] in vp['provider']['value'] and
                item['relevance_score'] >= vp['relevance_score']['value'] and
                item['uptime'] >= vp['uptime']['value']
            ):
                return item
        return None

    def _item_passes_policy(self, item: dict) -> bool:
        """
        Check if a cached item still meets policy qualifiers.

        :param item: MCP server metadata item.
        :return: True if all mandatory qualifiers are met.
        """
        vp = {m['name']: m for m in self.policy_metrics}
        return (
            item['verified'] == vp['verified']['value'] and
            item['provider'] in vp['provider']['value'] and
            item['relevance_score'] >= vp['relevance_score']['value'] and
            item['uptime'] >= vp['uptime']['value']
        )

    def load_cache(self) -> dict:
        """
        Load the local cache JSON or return empty structure if missing/corrupt.

        :return: Cache dict with 'cached_mcp' list.
        """
        if not os.path.exists(self.CACHE_FILE):
            return {"cached_mcp": []}
        try:
            return self._load_json(self.CACHE_FILE)
        except json.JSONDecodeError:
            return {"cached_mcp": []}

    def save_cache(self, cache: dict):
        """
        Persist cache dict to local JSON file.
        """
        self._save_json(self.CACHE_FILE, cache)

    def update_cache(self, item: dict, criteria: dict):
        """
        Add or refresh a cache entry for a verified item.
        Skips update if existing entry is younger than 72 hours.

        :param item: MCP server metadata item.
        :param criteria: Discovery criteria used.
        """
        endpoint = item['url']
        cache = self.load_cache()
        now = datetime.now()
        cutoff = now - timedelta(hours=72)

        # Check existing entry by item ID
        existing = next(
            (e for e in cache.get("cached_mcp", [])
             if e.get("data_item", {}).get("id") == item["id"]),
            None
        )
        # If exists and still fresh, do nothing
        if existing:
            last = datetime.strptime(existing['last_cached'], "%d.%m.%Y %H:%M:%S")
            if last > cutoff:
                return

        # Build new entry
        entry = {
            "mcp_endpoint": endpoint,
            "met_protocol_criteria": True,
            "last_cached": now.strftime("%d.%m.%Y %H:%M:%S"),
            "criteria": criteria,
            "data_item": item
        }

        # Replace existing or append new
        if existing:
            idx = cache["cached_mcp"].index(existing)
            cache["cached_mcp"][idx] = entry
        else:
            cache.setdefault("cached_mcp", []).append(entry)

        # Save updated cache
        self.save_cache(cache)

    def load_cached_endpoint(self) -> str | None:
        """
        Retrieve the first cached MCP endpoint that previously passed policy.

        :return: Endpoint URL or None.
        """
        cache = self.load_cache()
        for e in cache.get("cached_mcp", []):
            if e.get("met_protocol_criteria"):
                return e["mcp_endpoint"]
        return None

    def get_verifiable_mcp_endpoint(self) -> str | None:
        """
        Orchestrate endpoint resolution:
        1) Live discovery and policy matching
        2) Cache update
        3) Fallback to cached entries

        :return: Verified MCP endpoint URL or None.
        """
        criteria = {
            "limit": 3,
            "q": "recipe",
            "tags": "nutrition",
            "type": "tool",
            "verified": "true"
        }

        # 1) live discovery
        live_item = self.match_policy_and_get_url()
        if live_item:
            # Print registered MCP info
            mcp_info = {
                "name": live_item["name"],
                "endpoint_url": live_item["url"],
                "relevance_score": live_item["relevance_score"],
                "uptime": live_item["uptime"]
            }
            print("")
            print("  ---------------REGISTERED MCP SERVER INFORMATION FOR NUTRITION AND RECIPES-------------------")
            print("")
            print(" ", mcp_info)
            print("")
            print("  ---------------END-------------------")
            print("")

            # Update cache if enabled
            if self.policies.get("cache_mcp_servers_policy"):
                self.update_cache(live_item, criteria)

            return live_item['url']

        # 2) fallback to cache
        print("\n  WARNING !!!!!!! Live discovery failed; attempting policy check on cached entry…")
        cache = self.load_cache()
        for entry in cache.get("cached_mcp", []):
            item = entry.get("data_item")
            if item and self._item_passes_policy(item):
                print("")
                print("  ---------------USING CACHED MCP SERVER INFORMATION-------------------")
                print("")
                print(" ", {
                    "name": item["name"],
                    "endpoint_url": entry["mcp_endpoint"],
                    "relevance_score": item["relevance_score"],
                    "uptime": item["uptime"]
                })
                print("")
                print("  ---------------END-------------------")
                print("")
                return entry["mcp_endpoint"]

        # 3) nothing left
        return None
