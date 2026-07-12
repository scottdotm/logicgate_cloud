"""Passive external reconnaissance scanner for SMB domains."""

import asyncio
import socket
import ssl
from datetime import UTC, datetime
from typing import Any

import httpx
from dns import resolver

from logicgate_cloud.security_toolkit.common.exceptions import InvalidDomainError

# Top 30 ports that are most relevant for SMB external posture checks.
TOP_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3389, 5432, 5900, 8080, 8443]

SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
]


class ExternalScanner:
    """Passive, non-intrusive external scanner."""

    def __init__(self, timeout: float = 10.0, port_timeout: float = 2.0):
        self.timeout = timeout
        self.port_timeout = port_timeout

    async def scan(self, domain: str) -> dict[str, Any]:
        """Run a complete external scan and return structured results."""
        try:
            domain = self._normalize_domain(domain)
        except ValueError as exc:
            raise InvalidDomainError(f"Invalid domain: {domain}") from exc

        checks = []
        findings = []

        # DNS check
        dns_result = await self._check_dns(domain)
        checks.append(dns_result)
        findings.extend(dns_result.get("findings", []))

        # SSL check
        ssl_result = await self._check_ssl(domain)
        checks.append(ssl_result)
        findings.extend(ssl_result.get("findings", []))

        # HTTP headers check (only if port 80/443 is open-ish)
        header_result = await self._check_headers(domain)
        checks.append(header_result)
        findings.extend(header_result.get("findings", []))

        # Open ports check
        port_result = await self._check_ports(domain)
        checks.append(port_result)
        findings.extend(port_result.get("findings", []))

        overall_score = self._compute_score(findings)

        return {
            "domain": domain,
            "overall_score": overall_score,
            "rating": self._score_to_rating(overall_score),
            "checks": checks,
            "findings": findings,
        }

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        domain = domain.strip().lower()
        if domain.startswith(("http://", "https://")):
            domain = domain.split("//", 1)[1]
        if "/" in domain:
            domain = domain.split("/", 1)[0]
        if not domain or "." not in domain:
            raise ValueError("domain must contain a dot")
        return domain

    async def _check_dns(self, domain: str) -> dict[str, Any]:
        """Check DNS records and email security."""
        findings = []
        records = {"a": [], "mx": [], "txt": [], "ns": []}

        try:
            records["a"] = [str(r) for r in await asyncio.to_thread(resolver.resolve, domain, "A")]
        except Exception:
            findings.append(
                {
                    "nist_function": "ID",
                    "nist_category": "Asset Management",
                    "severity": "high",
                    "title": "Domain has no resolvable A record",
                    "description": f"The domain {domain} does not resolve to an IPv4 address.",
                    "recommendation": "Verify DNS configuration or confirm the domain is no longer in use.",
                    "effort": "small",
                }
            )

        try:
            records["mx"] = [
                str(r) for r in await asyncio.to_thread(resolver.resolve, domain, "MX")
            ]
        except Exception:
            records["mx"] = []

        try:
            records["txt"] = [
                str(r) for r in await asyncio.to_thread(resolver.resolve, domain, "TXT")
            ]
        except Exception:
            records["txt"] = []

        try:
            records["ns"] = [
                str(r) for r in await asyncio.to_thread(resolver.resolve, domain, "NS")
            ]
        except Exception:
            records["ns"] = []

        if records["mx"]:
            spf_present = any("v=spf1" in txt for txt in records["txt"])
            dmarc_present = any("v=DMARC1" in txt for txt in records["txt"])

            if not spf_present:
                findings.append(
                    {
                        "nist_function": "PR",
                        "nist_category": "Email Security",
                        "severity": "medium",
                        "title": "SPF record missing",
                        "description": "No SPF TXT record was found for the domain, which can allow email spoofing.",
                        "recommendation": "Publish an SPF record that authorizes your mail servers and ends with -all or ~all.",
                        "effort": "small",
                    }
                )
            if not dmarc_present:
                findings.append(
                    {
                        "nist_function": "PR",
                        "nist_category": "Email Security",
                        "severity": "medium",
                        "title": "DMARC record missing",
                        "description": "No DMARC TXT record was found, reducing protection against phishing and spoofing.",
                        "recommendation": "Publish a DMARC policy starting with p=none and move to p=quarantine/reject after validation.",
                        "effort": "small",
                    }
                )

        return {
            "name": "dns",
            "records": records,
            "findings": findings,
        }

    async def _check_ssl(self, domain: str) -> dict[str, Any]:
        """Check SSL/TLS certificate and configuration."""
        findings = []
        cert_info = {}

        try:
            context = ssl.create_default_context()
            with (
                socket.create_connection((domain, 443), timeout=self.timeout) as sock,
                context.wrap_socket(sock, server_hostname=domain) as ssock,
            ):
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()

                cert_info = {
                    "subject": cert.get("subject"),
                    "issuer": cert.get("issuer"),
                    "not_after": cert.get("notAfter"),
                    "not_before": cert.get("notBefore"),
                    "cipher": cipher[0] if cipher else None,
                    "tls_version": version,
                }

                not_after = cert.get("notAfter")
                if not_after:
                    expiry = ssl.cert_time_to_seconds(not_after)
                    days_left = (expiry - datetime.now(UTC).timestamp()) / 86400
                    if days_left < 0:
                        findings.append(
                            {
                                "nist_function": "PR",
                                "nist_category": "Data Security",
                                "severity": "critical",
                                "title": "SSL certificate expired",
                                "description": f"The SSL certificate for {domain} expired {abs(int(days_left))} days ago.",
                                "recommendation": "Renew and install a valid SSL certificate immediately.",
                                "effort": "small",
                            }
                        )
                    elif days_left < 30:
                        findings.append(
                            {
                                "nist_function": "PR",
                                "nist_category": "Data Security",
                                "severity": "medium",
                                "title": "SSL certificate expiring soon",
                                "description": f"The SSL certificate for {domain} expires in {int(days_left)} days.",
                                "recommendation": "Renew the SSL certificate before it expires.",
                                "effort": "small",
                            }
                        )

                if version in ("TLSv1", "TLSv1.1"):
                    findings.append(
                        {
                            "nist_function": "PR",
                            "nist_category": "Data Security",
                            "severity": "high",
                            "title": "Outdated TLS version enabled",
                            "description": f"The server supports {version}, which is deprecated and insecure.",
                            "recommendation": "Disable TLS 1.0/1.1 and require TLS 1.2 or higher.",
                            "effort": "small",
                        }
                    )

        except TimeoutError:
            findings.append(
                {
                    "nist_function": "PR",
                    "nist_category": "Data Security",
                    "severity": "info",
                    "title": "HTTPS not available",
                    "description": f"Could not connect to {domain}:443; HTTPS may not be configured.",
                    "recommendation": "Enable HTTPS on the domain if it serves web traffic.",
                    "effort": "small",
                }
            )
        except Exception as exc:
            findings.append(
                {
                    "nist_function": "PR",
                    "nist_category": "Data Security",
                    "severity": "info",
                    "title": "SSL check inconclusive",
                    "description": f"Could not complete SSL validation for {domain}: {str(exc)}",
                    "recommendation": "Verify the server supports HTTPS on port 443.",
                    "effort": "small",
                }
            )

        return {
            "name": "ssl",
            "cert_info": cert_info,
            "findings": findings,
        }

    async def _check_headers(self, domain: str) -> dict[str, Any]:
        """Check HTTP security headers on the HTTPS endpoint."""
        findings = []
        headers = {}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(f"https://{domain}")
                headers = {k.lower(): v for k, v in response.headers.items()}
        except Exception as exc:
            return {
                "name": "headers",
                "headers": {},
                "findings": [
                    {
                        "nist_function": "PR",
                        "nist_category": "Platform Security",
                        "severity": "info",
                        "title": "Could not retrieve HTTP headers",
                        "description": f"Header check failed for https://{domain}: {str(exc)}",
                        "recommendation": "Ensure the HTTPS endpoint is reachable and returns a valid response.",
                        "effort": "small",
                    }
                ],
            }

        for header in SECURITY_HEADERS:
            if header not in headers:
                findings.append(
                    {
                        "nist_function": "PR",
                        "nist_category": "Platform Security",
                        "severity": "low",
                        "title": f"Missing {header} header",
                        "description": f"The HTTPS response does not include the {header} security header.",
                        "recommendation": f"Configure the {header} HTTP response header to improve browser-side security.",
                        "effort": "small",
                    }
                )

        if "strict-transport-security" not in headers:
            findings.append(
                {
                    "nist_function": "PR",
                    "nist_category": "Data Security",
                    "severity": "medium",
                    "title": "HSTS header missing",
                    "description": "The Strict-Transport-Security header is missing, allowing downgrade attacks.",
                    "recommendation": "Add an HSTS header with max-age of at least 31536000 and includeSubDomains.",
                    "effort": "small",
                }
            )

        return {
            "name": "headers",
            "headers": headers,
            "findings": findings,
        }

    async def _check_ports(self, domain: str) -> dict[str, Any]:
        """Check a small set of common external ports."""
        findings = []
        open_ports = []

        async def probe_port(port: int) -> int | None:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(domain, port),
                    timeout=self.port_timeout,
                )
                writer.close()
                await writer.wait_closed()
                return port
            except Exception:
                return None

        results = await asyncio.gather(*[probe_port(p) for p in TOP_PORTS])
        open_ports = [p for p in results if p is not None]

        risky_ports = {
            21: "FTP",
            23: "Telnet",
            445: "SMB",
            3389: "RDP",
            5900: "VNC",
        }

        for port in open_ports:
            if port in risky_ports:
                findings.append(
                    {
                        "nist_function": "PR",
                        "nist_category": "Network Security",
                        "severity": "high",
                        "title": f"Exposed {risky_ports[port]} service on port {port}",
                        "description": f"The service {risky_ports[port]} is reachable from the public internet on port {port}.",
                        "recommendation": "Restrict access to a VPN or allow-list; disable the service if not required.",
                        "effort": "medium",
                    }
                )

        if 443 not in open_ports and 80 not in open_ports:
            findings.append(
                {
                    "nist_function": "PR",
                    "nist_category": "Network Security",
                    "severity": "info",
                    "title": "No web ports detected",
                    "description": "Neither HTTP (80) nor HTTPS (443) ports responded to the probe.",
                    "recommendation": "If the domain hosts a website, verify firewall and hosting configuration.",
                    "effort": "small",
                }
            )

        return {
            "name": "ports",
            "open_ports": open_ports,
            "findings": findings,
        }

    @staticmethod
    def _compute_score(findings: list[dict[str, Any]]) -> float:
        """Compute a 0-5 overall score from findings."""
        if not findings:
            return 5.0

        severity_weights = {
            "critical": 2.0,
            "high": 1.0,
            "medium": 0.5,
            "low": 0.25,
            "info": 0.0,
        }
        total_penalty = sum(severity_weights.get(f.get("severity", "info"), 0.0) for f in findings)
        score = max(0.0, 5.0 - total_penalty)
        return round(score, 1)

    @staticmethod
    def _score_to_rating(score: float) -> str:
        if score >= 4.5:
            return "Excellent"
        if score >= 3.5:
            return "Good"
        if score >= 2.5:
            return "Fair"
        if score >= 1.5:
            return "Poor"
        return "Critical"
