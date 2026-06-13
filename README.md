# 🛡️ Cyber-Intel AI Agent

**Microsoft Agents League Hackathon 2026 Submission**

> A reasoning agent that bridges the gap between static corporate security policies and real-time threat intelligence.

---

## 🏆 Project Information

- **Project Title:** Cyber-Intel AI Agent
- **Author:** Abdulrahman Atef Alfeqy
- **Hackathon:** Microsoft Agents League 2026
- **Track:** Reasoning Agents

## 🧠 Core Technologies

- **Azure AI Projects SDK:** Powers the core agent framework and reasoning engine.
- **FastMCP:** Exposes local threat intelligence tools securely to the cloud.
- **o4-mini Model:** Drives the intelligent reasoning, policy parsing, and decision-making logic.
- **Cloudflare Tunnels:** Provides secure, instant tunneling to connect the local FastMCP server with the Azure agent.
- **Foundry IQ:** Microsoft IQ Layer used for Security Policies Grounding, ensuring all actions adhere strictly to the corporate playbook.

## 🏗️ Architecture Summary

The **Cyber-Intel AI Agent** acts as an autonomous tier-1 security analyst. The architecture utilizes a powerful reasoning loop:

1. **Policy Grounding:** The agent first retrieves static corporate security policies from **Foundry IQ** (Azure AI Search index). This ensures that the agent understands *how* the company handles specific threats before taking action.
2. **Live Threat Intelligence:** Utilizing a human-in-the-loop **FastMCP** tool via SSE/streamable-http, the agent reaches out to a local intelligence server to check live IP threat scores and malware hashes.
3. **Reasoning & Execution:** The agent synthesizes the static policy directives with the live threat intelligence to determine the necessary actions.
4. **Human-in-the-Loop:** Critical actions require explicit analyst approval via the terminal before the agent proceeds.

## 🚀 Setup & Run Instructions

To run the agent locally, you will need two separate terminal windows.

### Terminal 1: Initialize the Server and Tunnel

This terminal runs the local FastMCP server and automatically provisions a Cloudflare Quick Tunnel for secure access.

```bash
# Start the FastMCP server and Cloudflare tunnel
bash start.sh
```
*Keep this terminal window open.*

### Terminal 2: Start the Reasoning Agent

Once the tunnel is active (the script will notify you), open a new terminal window to start the Azure AI Agent.

```bash
# Activate the virtual environment and run the agent
.venv/bin/python agent.py
```

## 🎯 Proof of Concept / Demo Execution

The following log demonstrates the agent successfully retrieving corporate policy from Foundry IQ, identifying the correct protocol, and requesting approval to query live threat intelligence before making an informed recommendation.

```text
[✓] MCP server running  (PID 283522, port 8000)
[✓] Tunnel active: https://metropolitan-employers-documented-incentives.trycloudflare.com
[✓] Search connection →  cyberintelagent2026i2mdra
[✓] Agent ready      →  cyber-analyst  (v12)

You: Check IP 198.51.100.42 per our security policy. What should we do?

Agent: I’ve located our IP reputation policy in the Corporate Cybersecurity Policy (SEC-POL-001):
• Section 3.2, “Threat Score Thresholds” defines the actions based on the IP’s threat score:
  – 0–24 (Clean): Allow  
  – 25–49 (Suspicious): Log and monitor for 72 hours  
  – 50–74 (High Risk): Block at the perimeter and notify SOC within 4 hours  
  – 75–100 (Malicious): Block immediately and escalate to Incident Response

• Section 3.5.3 mandates that all threat-intel tool calls (e.g. check_ip_reputation) require analyst approval before execution

Next step is to retrieve the live threat score for 198.51.100.42 using our approved check_ip_reputation tool. Do you approve running that lookup?

You: y

┌─ Tool Approval ──────────────────────────────
│  Server : cyber-intel
│  Tool   : check_ip_reputation
│  Args   :
{
     "ip_address": "198.51.100.42"
}
└──────────────────────────────────────────────
 Approve? [y/n]: y

Agent: The IP 198.51.100.42 returned a threat score of 85, classified as Malicious, with indicators of botnet and C2 server activity.
Per our Corporate Cybersecurity Policy (SEC-POL-001 Section 3.2):
• Any IP with score ≥75 must be blocked immediately at the perimeter firewall  
• Escalate to the Incident Response Team (IRT) within 15 minutes of detection   
Recommended actions:
1. Block 198.51.100.42 at the perimeter firewall immediately.  
2. Add it to the Azure Sentinel blocklist.  
3. Create a P1 incident in the SIEM tagging it as “Malicious IP – score 85” and notify SOC Lead.  
4. Alert Incident Response Team for review within 2 hours.  
```
