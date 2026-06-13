"""
Cyber-Intel AI Agent  ·  Microsoft Hackathon 2026
--------------------------------------------------
Combines Azure AI Foundry IQ (knowledge base) with a local FastMCP threat
intelligence server in a single native azure.ai.projects agent instance.

Run start.sh first, then:
    .venv/bin/python agent.py
"""

import json
import os
import sys
import time

import openai
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchQueryType,
    AzureAISearchTool,
    AzureAISearchToolResource,
    ConnectionType,
    MCPTool,
    PromptAgentDefinition,
)
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import InteractiveBrowserCredential
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = 3
RETRY_BASE_SECS = 2


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"[CONFIG ERROR] '{key}' is not set in .env")
        print("               Copy .env.template → .env and fill in your values.")
        sys.exit(1)
    return val


def _optional_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _validate_url(key: str, value: str, *, suffix: str | None = None) -> str:
    value = value.rstrip("/")
    if not value.startswith("https://"):
        print(f"[CONFIG ERROR] '{key}' must start with https://")
        print(f"               Current value: {value}")
        sys.exit(1)
    if suffix and not value.endswith(suffix):
        print(f"[CONFIG ERROR] '{key}' must end with {suffix}")
        print(f"               Current value: {value}")
        sys.exit(1)
    return value


PROJECT_ENDPOINT = _require("PROJECT_ENDPOINT")
SEARCH_ENDPOINT = _validate_url("SEARCH_ENDPOINT", _require("SEARCH_ENDPOINT"))
TENANT_ID = _require("TENANT_ID")
MODEL = _require("MODEL_DEPLOYMENT_NAME")
KB_NAME = _require("KNOWLEDGE_BASE_NAME")
SEARCH_INDEX_NAME = os.getenv("KNOWLEDGE_BASE_INDEX_NAME", f"ks-{KB_NAME}-index")
MCP_SERVER_URL = _validate_url("MCP_SERVER_URL", _require("MCP_SERVER_URL"), suffix="/mcp")
AGENT_NAME = os.getenv("AGENT_NAME", "cyber-analyst")
SEARCH_CONNECTION_NAME = os.getenv("AZURE_SEARCH_CONNECTION_NAME", "").strip()
DELETE_AGENT_ON_EXIT = _optional_bool("DELETE_AGENT_ON_EXIT", True)

AGENT_INSTRUCTIONS = f"""You are a Cybersecurity Analyst. Your primary goal is to provide accurate \
threat assessments grounded in company security policies and live threat intelligence.

CRITICAL RULES:
- ALWAYS search the "{KB_NAME}" knowledge base (Azure AI Search index) FIRST before using any \
cyber-intel tools.
- If the knowledge base contains no relevant policy, state that clearly before proceeding.
- Use check_ip_reputation and analyze_malware_hash ONLY after querying the knowledge base.
- Combine policy guidance with threat intelligence for a comprehensive assessment.
- Always cite the policy section when available.
- When a tool requires approval, wait for the operator to approve it."""


def _find_search_connection(project_client: AIProjectClient) -> str:
    """Return the Foundry CognitiveSearch connection name for AzureAISearchTool."""
    search_host = SEARCH_ENDPOINT.removeprefix("https://").rstrip("/")
    all_search: list = []

    for conn in project_client.connections.list():
        conn_type = getattr(conn, "type", None)
        if conn_type not in {ConnectionType.AZURE_AI_SEARCH, "CognitiveSearch"}:
            continue
        all_search.append(conn)

    if not all_search:
        print("\n[CONFIG ERROR] No Azure AI Search connection found in this Foundry project.")
        print("  Fix in portal:")
        print("    Foundry → Overview → Connected resources → Add connection")
        print("    Choose: Azure AI Search → cyberintel-agent-2026 → API Key")
        sys.exit(1)

    if SEARCH_CONNECTION_NAME:
        for conn in all_search:
            if getattr(conn, "name", "") == SEARCH_CONNECTION_NAME:
                return conn.name
        names = ", ".join(getattr(c, "name", "?") for c in all_search)
        print(f"\n[CONFIG ERROR] Connection '{SEARCH_CONNECTION_NAME}' not found.")
        print(f"  Available Search connections: {names}")
        sys.exit(1)

    endpoint_matches = [
        c for c in all_search
        if search_host in (getattr(c, "target", "") or "").removeprefix("https://").rstrip("/")
        or (getattr(c, "target", "") or "").removeprefix("https://").rstrip("/") in search_host
    ]
    candidates = endpoint_matches or all_search

    for conn in candidates:
        if getattr(conn, "is_default", False):
            return conn.name

    if len(candidates) > 1:
        names = ", ".join(getattr(c, "name", "?") for c in candidates)
        print(f"[INFO] Multiple Search connections ({names}); using '{candidates[0].name}'.")

    return candidates[0].name


def _verify_search_connection(project_client: AIProjectClient, connection_name: str) -> None:
    """Confirm the Search connection has a stored API key before creating the agent."""
    try:
        conn = project_client.connections.get(
            connection_name, include_credentials=True
        )
    except HttpResponseError as exc:
        print(f"\n[CONFIG ERROR] Could not read connection '{connection_name}': {exc.message}")
        sys.exit(1)

    creds = getattr(conn, "credentials", None)
    api_key = getattr(creds, "api_key", None) if creds else None
    if api_key:
        print(f"✓ Search API key    →  present in connection '{connection_name}'")
        return

    print(f"\n[CONFIG ERROR] Connection '{connection_name}' has no API key stored.")
    print("  Fix in Foundry portal:")
    print("    Overview → Connected resources → cyberintelagent2026i2mdra")
    print("    Edit authentication → paste Primary admin key from Search → Save")
    sys.exit(1)


def _build_knowledge_tool(connection_name: str) -> AzureAISearchTool:
    """
    Foundry IQ indexes are queried via AzureAISearchTool (official Microsoft sample).
    The KB MCP endpoint rejects project-connection auth with 401 in this setup.
    """
    return AzureAISearchTool(
        name=KB_NAME,
        description=f"Corporate security policies from Foundry IQ knowledge base '{KB_NAME}'",
        azure_ai_search=AzureAISearchToolResource(
            indexes=[
                AISearchIndexResource(
                    project_connection_id=connection_name,
                    index_name=SEARCH_INDEX_NAME,
                    query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                    top_k=5,
                )
            ]
        ),
    )


def _build_cyber_tool() -> MCPTool:
    return MCPTool(
        server_label="cyber-intel",
        server_url=MCP_SERVER_URL,
        require_approval="always",
    )


def _response_output(response) -> list:
    output = getattr(response, "output", None)
    return output if output else []


def _find_mcp_approval_request(response):
    for item in _response_output(response):
        if getattr(item, "type", None) == "mcp_approval_request":
            return item
    return None


def _diagnose_bad_request(exc: openai.BadRequestError) -> None:
    msg = str(exc)
    if "index" in msg.lower() and "not found" in msg.lower():
        print("\n[KB ERROR] Search index not found.")
        print(f"  Index in use : {SEARCH_INDEX_NAME}")
        print("  Likely fix   : Set KNOWLEDGE_BASE_INDEX_NAME in .env")
        print("                 (Foundry → Knowledge → security-policies → check index name)")
    elif "knowledgebases" in msg and "401" in msg:
        print("\n[KB AUTH ERROR] Foundry IQ MCP auth failed (401).")
        print("  Note: This project uses AzureAISearchTool instead — re-run agent.py.")
    elif "Connection refused" in msg or (
        "tool_user_error" in msg and "trycloudflare" in msg
    ):
        print("\n[MCP ERROR] Azure cannot reach the CyberIntel MCP server.")
        print(f"  Raw Error  : {msg}")
        print(f"  URL in use : {MCP_SERVER_URL}")
        print("  Likely fix : Re-run start.sh — the tunnel URL changes every restart.")
    elif "tool_user_error" in msg:
        print(f"\n[TOOL ERROR] {msg}")
    else:
        print(f"\n[REQUEST ERROR 400] {exc}")


def _diagnose_http_error(exc: HttpResponseError) -> None:
    if exc.status_code == 401:
        print("\n[AUTH ERROR] Token rejected by Azure.")
        print("  Fix : Re-run agent.py and complete the browser sign-in.")
    elif exc.status_code == 403:
        print("\n[PERMISSION ERROR] Your account lacks access to this resource.")
        print("  Fix : Check that your Azure account owns the Foundry project.")
    elif exc.status_code == 404:
        print(f"\n[NOT FOUND] {exc.message}")
        print("  Fix : Verify PROJECT_ENDPOINT, SEARCH_ENDPOINT, and index name in .env.")
    else:
        print(f"\n[AZURE HTTP {exc.status_code}] {exc.message}")


def _create_response(
    openai_client,
    *,
    conv_id: str,
    agent_name: str,
    input_val: str = "",
) -> object | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return openai_client.responses.create(
                conversation=conv_id,
                input=input_val,
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
            )

        except openai.BadRequestError as exc:
            _diagnose_bad_request(exc)
            return None

        except openai.RateLimitError:
            wait = 10 * attempt
            print(f"[RATE LIMIT] Waiting {wait} s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)

        except openai.APIConnectionError:
            if attempt >= MAX_RETRIES:
                print(f"[NETWORK ERROR] Unreachable after {MAX_RETRIES} attempts.")
                print("  Check your internet connection and that start.sh is running.")
                return None
            delay = RETRY_BASE_SECS ** attempt
            print(
                f"[NETWORK] Connection error — retrying in {delay} s "
                f"({attempt}/{MAX_RETRIES})..."
            )
            time.sleep(delay)

        except openai.APIStatusError as exc:
            if exc.status_code >= 500 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_SECS ** attempt
                print(
                    f"[SERVER ERROR {exc.status_code}] Retrying in {delay} s "
                    f"({attempt}/{MAX_RETRIES})..."
                )
                time.sleep(delay)
            else:
                print(f"[API ERROR {exc.status_code}] {exc.message}")
                return None

    return None


def _run_approval_loop(
    openai_client, response, *, agent_name: str, conv_id: str
) -> object | None:
    while True:
        approval_request = _find_mcp_approval_request(response)
        if approval_request is None:
            return response

        server_label = getattr(approval_request, "server_label", "unknown")
        tool_name = getattr(approval_request, "name", "unknown")
        raw_args = getattr(approval_request, "arguments", "{}")

        print("\n┌─ Tool Approval ──────────────────────────────")
        print(f"│  Server : {server_label}")
        print(f"│  Tool   : {tool_name}")
        try:
            pretty = json.dumps(json.loads(raw_args), indent=5)
            print(f"│  Args   :\n{pretty}")
        except (json.JSONDecodeError, TypeError):
            print(f"│  Args   : {raw_args}")
        print("└──────────────────────────────────────────────")

        try:
            decision = input("  Approve? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            decision = "n"

        openai_client.conversations.items.create(
            conversation_id=conv_id,
            items=[
                {
                    "type": "mcp_approval_response",
                    "approval_request_id": approval_request.id,
                    "approve": decision in {"y", "yes"},
                }
            ],
        )

        response = _create_response(
            openai_client,
            conv_id=conv_id,
            agent_name=agent_name,
        )
        if response is None:
            return None


def main() -> None:
    print("\n" + "═" * 52)
    print("  Cyber-Intel AI Agent  —  Microsoft Hackathon 2026")
    print("═" * 52)
    print(f"  Model     : {MODEL}")
    print(f"  KB        : {KB_NAME}")
    print(f"  Index     : {SEARCH_INDEX_NAME}")
    print(f"  MCP URL   : {MCP_SERVER_URL}")
    print("═" * 52 + "\n")

    print("Opening browser for Azure login (close when done)...")
    credential = InteractiveBrowserCredential(tenant_id=TENANT_ID)

    project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    openai_client = project_client.get_openai_client()
    agent = None
    created_agent = False

    try:
        search_connection_name = _find_search_connection(project_client)
        print(f"✓ Search connection →  {search_connection_name}")
        _verify_search_connection(project_client, search_connection_name)

        agent = project_client.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL,
                instructions=AGENT_INSTRUCTIONS,
                tools=[_build_knowledge_tool(search_connection_name), _build_cyber_tool()],
            ),
        )
        created_agent = True
        print(f"✓ Agent ready      →  {agent.name}  (v{agent.version})")

        conv = openai_client.conversations.create(items=[])
        print(f"✓ Conversation ID  →  {conv.id}")
        print('\nType "exit" to quit.\n' + "─" * 52)

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break

            openai_client.conversations.items.create(
                conversation_id=conv.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )

            response = _create_response(
                openai_client,
                conv_id=conv.id,
                agent_name=agent.name,
            )
            if response is None:
                print("  (Skipping turn — see error above)\n")
                continue

            response = _run_approval_loop(
                openai_client,
                response,
                agent_name=agent.name,
                conv_id=conv.id,
            )
            if response is None:
                print("  (Approval cycle failed — see error above)\n")
                continue

            output_text = getattr(response, "output_text", None)
            if output_text:
                print(f"\nAgent: {output_text}")
            else:
                print("\nAgent: (No text response — check Foundry traces in the portal.)")

    except ClientAuthenticationError as exc:
        print("\n[AUTH ERROR] Azure rejected the credential.")
        print(f"  Details : {exc.message}")
        print("  Fix     : Re-run agent.py and complete browser sign-in.")
        sys.exit(1)

    except HttpResponseError as exc:
        _diagnose_http_error(exc)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")

    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {type(exc).__name__}: {exc}")
        raise

    finally:
        if created_agent and agent is not None and DELETE_AGENT_ON_EXIT:
            try:
                project_client.agents.delete_version(
                    agent_name=agent.name,
                    agent_version=agent.version,
                )
                print("\n✓ Agent version deleted.")
            except Exception as exc:
                print("\n[WARN] Could not auto-delete agent version.")
                print("       Delete manually in Foundry portal:")
                print(f"       Name={agent.name}  Version={agent.version}")
                print(f"       Error: {exc}")
        try:
            openai_client.close()
            project_client.close()
        except Exception:
            pass
        print("Goodbye.\n")


if __name__ == "__main__":
    main()
