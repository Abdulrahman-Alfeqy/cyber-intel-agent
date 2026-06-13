# Corporate Cybersecurity Policy
**Document ID:** SEC-POL-001  
**Version:** 3.1  
**Effective Date:** 2026-01-01  
**Owner:** Information Security Office  
**Classification:** Internal Use Only

---

## 1. IP Reputation & Network Threat Policy (Section 3.2)

### 1.1 Threat Score Thresholds

All IP addresses interacting with corporate systems must be evaluated against the following thresholds:

| Threat Score | Classification | Required Action |
|---|---|---|
| 0 – 24 | Clean | Allow – no action required |
| 25 – 49 | Suspicious | Log and monitor for 72 hours |
| 50 – 74 | High Risk | Block at perimeter firewall; notify SOC within 4 hours |
| 75 – 100 | Malicious | Block immediately; escalate to Incident Response Team |

### 1.2 Malicious IP Handling

Any IP with a threat score of **75 or above** must be:

1. Blocked at the perimeter firewall within **15 minutes** of detection.
2. Added to the corporate blocklist maintained in Azure Sentinel.
3. Reported to the SOC via the SIEM ticketing system (Priority P1).
4. Reviewed by the Incident Response Team within **2 hours**.

### 1.3 Botnet and C2 Server Indicators

IP addresses associated with the following categories are automatically classified as **Malicious (score 100)**:

- Command-and-Control (C2) servers
- Botnet infrastructure
- Known ransomware distribution nodes
- Tor exit nodes (unless specifically whitelisted by the CISO)

Immediate isolation of any endpoint that has communicated with a confirmed C2 address is **mandatory** (see Section 5 – Incident Response).

---

## 2. Malware Incident Response Policy (Section 4.1)

### 2.1 Severity Classification

| Severity | Detection Ratio | Action SLA |
|---|---|---|
| Critical | > 40/60 AV engines | Isolate endpoint within 15 min; P1 ticket |
| High | 20–40/60 AV engines | Isolate endpoint within 1 hour; P2 ticket |
| Medium | 5–20/60 AV engines | Investigate within 4 hours; P3 ticket |
| Low | < 5/60 AV engines | Log and schedule review within 24 hours |

### 2.2 Malware Hash Analysis Requirements

When a suspicious file hash (MD5, SHA1, or SHA256) is identified:

1. Submit the hash to the corporate threat intelligence platform for analysis.
2. Cross-reference against known malware families in the internal IOC database.
3. If the hash matches a **known malware family** (e.g., Emotet, Ryuk, TrickBot, Cobalt Strike):
   - Immediately quarantine the affected endpoint.
   - Preserve forensic artifacts before remediation.
   - Notify the Data Protection Officer if PII may have been exfiltrated.

### 2.3 Emotet-Specific Protocol

Due to Emotet's credential-harvesting and lateral movement capabilities, detection of Emotet requires:

1. **Immediate network isolation** of the affected host.
2. Password reset for **all accounts** that were active on the host in the past 30 days.
3. Review of email gateway logs for phishing campaigns originating from or targeting the host.
4. Threat hunt across all endpoints for related IOCs (file hashes, registry keys, network beacons).

---

## 3. Threat Intelligence Tool Usage Policy (Section 3.5)

### 3.1 Authorised Tools

The following tools are approved for threat investigation:

- **check_ip_reputation** – for evaluating IP address threat scores.
- **analyze_malware_hash** – for identifying malware families and detection ratios.

### 3.2 Mandatory Sequence

Analysts **must** follow this sequence for every investigation:

1. Consult the security policies knowledge base first to determine applicable policy.
2. Use approved threat intelligence tools to gather live data.
3. Combine policy guidance with tool output to produce a final risk assessment.
4. Document findings in the SIEM with policy references cited.

### 3.3 Tool Call Approval

All threat intelligence tool calls require analyst approval before execution. Analysts are responsible for verifying that the tool call parameters are correct before approving.

---

## 4. Data Handling & Escalation (Section 6.1)

### 4.1 Sensitive Data in Investigations

- Hash values, IP addresses, and investigation artefacts are classified as **Confidential**.
- Do not share investigation data outside the SOC without written approval from the CISO.
- All investigation activity must be logged in the SIEM audit trail.

### 4.2 Escalation Contacts

| Role | Contact | Availability |
|---|---|---|
| SOC Lead | soc-lead@company.internal | 24/7 |
| Incident Response Team | irt@company.internal | 24/7 |
| CISO | ciso@company.internal | Business hours + P1 on-call |
| Data Protection Officer | dpo@company.internal | Business hours |

---

## 5. Policy Compliance

Failure to follow this policy may result in disciplinary action. All incidents must be documented with policy section references in the final report.

**Last reviewed:** 2026-06-01  
**Next review due:** 2027-01-01
