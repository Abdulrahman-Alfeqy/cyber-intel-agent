"""
CyberIntel MCP Server  ·  Microsoft Hackathon 2026
---------------------------------------------------
Exposes threat-intelligence tools via FastMCP (streamable-http).

Start this via start.sh — do not run directly unless testing.
MCP endpoint: http://0.0.0.0:<MCP_PORT>/mcp   (default port: 8000)
"""

import os

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(name="CyberIntel")


@mcp.tool()
def check_ip_reputation(ip_address: str) -> dict:
    """
    Check the reputation of an IP address.
    Returns threat score (0–100), category, and associated threat types.
    Replace the mock data below with a real TI API (e.g. VirusTotal, Shodan).
    """
    return {
        "ip_address": ip_address,
        "threat_score": 85,
        "category": "malicious",
        "last_reported": "2026-06-10",
        "associated_threats": ["botnet", "c2_server"],
    }


@mcp.tool()
def analyze_malware_hash(hash_string: str) -> dict:
    """
    Analyze a malware hash (MD5, SHA1, or SHA256).
    Returns AV detection ratio, malware family, and severity.
    Replace the mock data below with a real API (e.g. MalwareBazaar, VirusTotal).
    """
    return {
        "hash": hash_string,
        "detection_ratio": "45/60",
        "malware_family": "Emotet",
        "first_seen": "2026-06-01",
        "severity": "high",
    }


if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    print(f"Starting CyberIntel MCP server on http://{host}:{port}/mcp")
    mcp.run(transport="streamable-http", host=host, port=port)
