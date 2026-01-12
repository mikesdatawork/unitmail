"""
DNS configuration checker for unitMail.

This module provides comprehensive DNS verification for email
server configuration, including SPF, DKIM, DMARC, MX, and PTR records.
"""

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

import dns.resolver
import dns.reversename

from src.common.exceptions import DNSError, DNSLookupError

logger = logging.getLogger(__name__)


class RecordStatus(Enum):
    """Status of a DNS record check."""

    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DNSCheckResult:
    """Result of a single DNS check."""

    record_type: str
    status: RecordStatus
    value: Optional[str] = None
    expected: Optional[str] = None
    message: str = ""
    details: dict = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        """Check if the result indicates a valid record."""
        return self.status == RecordStatus.VALID


@dataclass
class SPFRecord:
    """Parsed SPF record."""

    raw: str
    version: str = "spf1"
    mechanisms: list[str] = field(default_factory=list)
    modifiers: dict[str, str] = field(default_factory=dict)
    all_qualifier: str = "~"  # ?, +, -, ~
    includes: list[str] = field(default_factory=list)
    ip4: list[str] = field(default_factory=list)
    ip6: list[str] = field(default_factory=list)
    mx: bool = False
    a: bool = False


@dataclass
class DMARCRecord:
    """Parsed DMARC record."""

    raw: str
    version: str = "DMARC1"
    policy: str = "none"  # none, quarantine, reject
    subdomain_policy: str = ""
    pct: int = 100
    rua: list[str] = field(default_factory=list)  # Aggregate reports
    ruf: list[str] = field(default_factory=list)  # Forensic reports
    aspf: str = "r"  # SPF alignment (r=relaxed, s=strict)
    adkim: str = "r"  # DKIM alignment
    fo: str = "0"  # Failure reporting options
    ri: int = 86400  # Reporting interval


@dataclass
class MXRecord:
    """MX record information."""

    hostname: str
    priority: int
    ip_addresses: list[str] = field(default_factory=list)


@dataclass
class DNSHealthReport:
    """Complete DNS health report for a domain."""

    domain: str
    timestamp: str
    overall_status: RecordStatus
    spf: DNSCheckResult
    dkim: dict[str, DNSCheckResult] = field(default_factory=dict)
    dmarc: DNSCheckResult = field(default_factory=lambda: DNSCheckResult("DMARC", RecordStatus.MISSING))
    mx: DNSCheckResult = field(default_factory=lambda: DNSCheckResult("MX", RecordStatus.MISSING))
    ptr: dict[str, DNSCheckResult] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            "domain": self.domain,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "checks": {
                "spf": {
                    "status": self.spf.status.value,
                    "value": self.spf.value,
                    "message": self.spf.message,
                },
                "dkim": {
                    selector: {
                        "status": result.status.value,
                        "value": result.value,
                        "message": result.message,
                    }
                    for selector, result in self.dkim.items()
                },
                "dmarc": {
                    "status": self.dmarc.status.value,
                    "value": self.dmarc.value,
                    "message": self.dmarc.message,
                },
                "mx": {
                    "status": self.mx.status.value,
                    "value": self.mx.value,
                    "message": self.mx.message,
                    "details": self.mx.details,
                },
                "ptr": {
                    ip: {
                        "status": result.status.value,
                        "value": result.value,
                        "message": result.message,
                    }
                    for ip, result in self.ptr.items()
                },
            },
            "recommendations": self.recommendations,
        }


class DNSChecker:
    """
    DNS configuration checker for email domains.

    Verifies SPF, DKIM, DMARC, MX, and PTR records to ensure
    proper email authentication and deliverability.
    """

    def __init__(
        self,
        resolver: Optional[str] = None,
        timeout: int = 5,
    ) -> None:
        """
        Initialize the DNS checker.

        Args:
            resolver: Custom DNS resolver address.
            timeout: DNS query timeout in seconds.
        """
        self._resolver = dns.resolver.Resolver()
        if resolver:
            self._resolver.nameservers = [resolver]
        self._resolver.lifetime = timeout

        logger.info("Initialized DNS checker")

    def _query(
        self,
        name: str,
        rdtype: str,
    ) -> list[str]:
        """
        Perform a DNS query.

        Args:
            name: DNS name to query.
            rdtype: Record type (A, AAAA, MX, TXT, PTR, etc.).

        Returns:
            List of record values.

        Raises:
            DNSLookupError: If query fails.
        """
        try:
            answers = self._resolver.resolve(name, rdtype)
            results = []

            for rdata in answers:
                if rdtype == "TXT":
                    # Concatenate TXT record strings
                    value = "".join(
                        s.decode("utf-8", errors="replace")
                        if isinstance(s, bytes) else s
                        for s in rdata.strings
                    )
                    results.append(value)
                elif rdtype == "MX":
                    results.append(f"{rdata.preference} {rdata.exchange}")
                else:
                    results.append(str(rdata))

            return results

        except dns.resolver.NXDOMAIN:
            raise DNSLookupError(name, rdtype, {"reason": "Domain not found"})
        except dns.resolver.NoAnswer:
            raise DNSLookupError(name, rdtype, {"reason": "No answer"})
        except dns.resolver.Timeout:
            raise DNSLookupError(name, rdtype, {"reason": "Timeout"})
        except Exception as e:
            raise DNSLookupError(name, rdtype, {"reason": str(e)})

    def check_spf(self, domain: str) -> DNSCheckResult:
        """
        Check SPF record for a domain.

        Args:
            domain: Domain to check.

        Returns:
            DNSCheckResult with SPF verification status.
        """
        try:
            txt_records = self._query(domain, "TXT")

            # Find SPF record
            spf_records = [
                r for r in txt_records
                if r.startswith("v=spf1")
            ]

            if not spf_records:
                return DNSCheckResult(
                    record_type="SPF",
                    status=RecordStatus.MISSING,
                    message="No SPF record found",
                )

            if len(spf_records) > 1:
                return DNSCheckResult(
                    record_type="SPF",
                    status=RecordStatus.WARNING,
                    value=spf_records[0],
                    message="Multiple SPF records found (should have only one)",
                )

            spf_record = spf_records[0]
            parsed = self._parse_spf(spf_record)

            # Check for common issues
            issues = []

            # Check for -all (hard fail) vs ~all (soft fail)
            if parsed.all_qualifier == "+":
                issues.append("Uses +all which allows any sender (insecure)")
            elif parsed.all_qualifier == "?":
                issues.append("Uses ?all which is neutral (not recommended)")
            elif parsed.all_qualifier == "~":
                issues.append("Uses ~all (softfail) - consider -all for stricter policy")

            # Check for too many DNS lookups (limit is 10)
            lookups = len(parsed.includes) + (1 if parsed.mx else 0) + (1 if parsed.a else 0)
            if lookups > 10:
                issues.append(f"Too many DNS lookups ({lookups}/10 max)")

            if issues:
                return DNSCheckResult(
                    record_type="SPF",
                    status=RecordStatus.WARNING,
                    value=spf_record,
                    message="; ".join(issues),
                    details={"parsed": parsed.__dict__},
                )

            return DNSCheckResult(
                record_type="SPF",
                status=RecordStatus.VALID,
                value=spf_record,
                message="SPF record is properly configured",
                details={"parsed": parsed.__dict__},
            )

        except DNSLookupError as e:
            return DNSCheckResult(
                record_type="SPF",
                status=RecordStatus.ERROR,
                message=f"DNS lookup failed: {e.details.get('reason', str(e))}",
            )

    def _parse_spf(self, record: str) -> SPFRecord:
        """Parse an SPF record into components."""
        parsed = SPFRecord(raw=record)

        parts = record.split()
        for part in parts:
            part_lower = part.lower()

            if part_lower.startswith("v="):
                parsed.version = part[2:]
            elif part_lower.startswith("include:"):
                parsed.includes.append(part[8:])
            elif part_lower.startswith("ip4:"):
                parsed.ip4.append(part[4:])
            elif part_lower.startswith("ip6:"):
                parsed.ip6.append(part[4:])
            elif part_lower == "mx":
                parsed.mx = True
            elif part_lower == "a":
                parsed.a = True
            elif part_lower in ["+all", "-all", "~all", "?all"]:
                parsed.all_qualifier = part[0]
            elif "=" in part:
                key, value = part.split("=", 1)
                parsed.modifiers[key] = value
            else:
                parsed.mechanisms.append(part)

        return parsed

    def check_dkim(
        self,
        domain: str,
        selector: str,
    ) -> DNSCheckResult:
        """
        Check DKIM record for a domain and selector.

        Args:
            domain: Domain to check.
            selector: DKIM selector.

        Returns:
            DNSCheckResult with DKIM verification status.
        """
        dkim_domain = f"{selector}._domainkey.{domain}"

        try:
            txt_records = self._query(dkim_domain, "TXT")

            if not txt_records:
                return DNSCheckResult(
                    record_type="DKIM",
                    status=RecordStatus.MISSING,
                    message=f"No DKIM record found for selector '{selector}'",
                    expected=dkim_domain,
                )

            dkim_record = txt_records[0]

            # Parse DKIM record
            parts = {}
            for part in dkim_record.split(";"):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    parts[key.strip()] = value.strip()

            # Validate required fields
            issues = []

            if "v" not in parts or parts["v"] != "DKIM1":
                issues.append("Missing or invalid version (should be v=DKIM1)")

            if "p" not in parts:
                issues.append("Missing public key (p=)")
            elif not parts["p"]:
                return DNSCheckResult(
                    record_type="DKIM",
                    status=RecordStatus.INVALID,
                    value=dkim_record,
                    message="DKIM key has been revoked (empty p= value)",
                )

            if "k" in parts and parts["k"] not in ["rsa", "ed25519"]:
                issues.append(f"Unsupported key type: {parts['k']}")

            if issues:
                return DNSCheckResult(
                    record_type="DKIM",
                    status=RecordStatus.WARNING,
                    value=dkim_record,
                    message="; ".join(issues),
                    details={"selector": selector, "parsed": parts},
                )

            return DNSCheckResult(
                record_type="DKIM",
                status=RecordStatus.VALID,
                value=dkim_record,
                message=f"DKIM record for selector '{selector}' is properly configured",
                details={"selector": selector, "parsed": parts},
            )

        except DNSLookupError as e:
            return DNSCheckResult(
                record_type="DKIM",
                status=RecordStatus.MISSING,
                message=f"DKIM record not found for selector '{selector}': {e.details.get('reason', str(e))}",
                expected=dkim_domain,
            )

    def check_dmarc(self, domain: str) -> DNSCheckResult:
        """
        Check DMARC record for a domain.

        Args:
            domain: Domain to check.

        Returns:
            DNSCheckResult with DMARC verification status.
        """
        dmarc_domain = f"_dmarc.{domain}"

        try:
            txt_records = self._query(dmarc_domain, "TXT")

            # Find DMARC record
            dmarc_records = [
                r for r in txt_records
                if r.startswith("v=DMARC1")
            ]

            if not dmarc_records:
                return DNSCheckResult(
                    record_type="DMARC",
                    status=RecordStatus.MISSING,
                    message="No DMARC record found",
                    expected=dmarc_domain,
                )

            dmarc_record = dmarc_records[0]
            parsed = self._parse_dmarc(dmarc_record)

            # Check for issues
            issues = []

            if parsed.policy == "none":
                issues.append("Policy is 'none' (monitoring only) - consider 'quarantine' or 'reject'")

            if not parsed.rua:
                issues.append("No aggregate report address (rua) configured")

            if parsed.pct < 100:
                issues.append(f"Only applying to {parsed.pct}% of messages")

            if issues:
                return DNSCheckResult(
                    record_type="DMARC",
                    status=RecordStatus.WARNING,
                    value=dmarc_record,
                    message="; ".join(issues),
                    details={"parsed": parsed.__dict__},
                )

            return DNSCheckResult(
                record_type="DMARC",
                status=RecordStatus.VALID,
                value=dmarc_record,
                message="DMARC record is properly configured",
                details={"parsed": parsed.__dict__},
            )

        except DNSLookupError as e:
            return DNSCheckResult(
                record_type="DMARC",
                status=RecordStatus.MISSING,
                message=f"DMARC record not found: {e.details.get('reason', str(e))}",
                expected=dmarc_domain,
            )

    def _parse_dmarc(self, record: str) -> DMARCRecord:
        """Parse a DMARC record into components."""
        parsed = DMARCRecord(raw=record)

        parts = record.split(";")
        for part in parts:
            part = part.strip()
            if "=" not in part:
                continue

            key, value = part.split("=", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "v":
                parsed.version = value
            elif key == "p":
                parsed.policy = value
            elif key == "sp":
                parsed.subdomain_policy = value
            elif key == "pct":
                try:
                    parsed.pct = int(value)
                except ValueError:
                    pass
            elif key == "rua":
                parsed.rua = [uri.strip() for uri in value.split(",")]
            elif key == "ruf":
                parsed.ruf = [uri.strip() for uri in value.split(",")]
            elif key == "aspf":
                parsed.aspf = value
            elif key == "adkim":
                parsed.adkim = value
            elif key == "fo":
                parsed.fo = value
            elif key == "ri":
                try:
                    parsed.ri = int(value)
                except ValueError:
                    pass

        return parsed

    def check_mx(self, domain: str) -> DNSCheckResult:
        """
        Check MX records for a domain.

        Args:
            domain: Domain to check.

        Returns:
            DNSCheckResult with MX verification status.
        """
        try:
            mx_records = self._query(domain, "MX")

            if not mx_records:
                return DNSCheckResult(
                    record_type="MX",
                    status=RecordStatus.MISSING,
                    message="No MX records found",
                )

            # Parse and resolve MX records
            mx_list = []
            for mx in mx_records:
                parts = mx.split()
                if len(parts) >= 2:
                    priority = int(parts[0])
                    hostname = parts[1].rstrip(".")

                    # Resolve A/AAAA records
                    ip_addresses = []
                    try:
                        for a_record in self._query(hostname, "A"):
                            ip_addresses.append(a_record)
                    except DNSLookupError:
                        pass

                    try:
                        for aaaa_record in self._query(hostname, "AAAA"):
                            ip_addresses.append(aaaa_record)
                    except DNSLookupError:
                        pass

                    mx_list.append(MXRecord(
                        hostname=hostname,
                        priority=priority,
                        ip_addresses=ip_addresses,
                    ))

            # Sort by priority
            mx_list.sort(key=lambda x: x.priority)

            # Check for issues
            issues = []

            # Check if any MX has no IP
            for mx in mx_list:
                if not mx.ip_addresses:
                    issues.append(f"MX '{mx.hostname}' has no A/AAAA records")

            # Check for localhost or private IPs
            for mx in mx_list:
                for ip in mx.ip_addresses:
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj.is_private:
                            issues.append(f"MX '{mx.hostname}' resolves to private IP {ip}")
                        if ip_obj.is_loopback:
                            issues.append(f"MX '{mx.hostname}' resolves to loopback {ip}")
                    except ValueError:
                        pass

            mx_value = "; ".join(
                f"{mx.priority} {mx.hostname}" for mx in mx_list
            )

            if issues:
                return DNSCheckResult(
                    record_type="MX",
                    status=RecordStatus.WARNING,
                    value=mx_value,
                    message="; ".join(issues),
                    details={"records": [mx.__dict__ for mx in mx_list]},
                )

            return DNSCheckResult(
                record_type="MX",
                status=RecordStatus.VALID,
                value=mx_value,
                message=f"Found {len(mx_list)} MX record(s)",
                details={"records": [mx.__dict__ for mx in mx_list]},
            )

        except DNSLookupError as e:
            return DNSCheckResult(
                record_type="MX",
                status=RecordStatus.ERROR,
                message=f"MX lookup failed: {e.details.get('reason', str(e))}",
            )

    def check_ptr(self, ip_address: str) -> DNSCheckResult:
        """
        Check PTR (reverse DNS) record for an IP address.

        Args:
            ip_address: IP address to check.

        Returns:
            DNSCheckResult with PTR verification status.
        """
        try:
            # Create reverse DNS name
            try:
                ip_obj = ipaddress.ip_address(ip_address)
                reverse_name = dns.reversename.from_address(ip_address)
            except ValueError as e:
                return DNSCheckResult(
                    record_type="PTR",
                    status=RecordStatus.ERROR,
                    message=f"Invalid IP address: {e}",
                )

            ptr_records = self._query(str(reverse_name), "PTR")

            if not ptr_records:
                return DNSCheckResult(
                    record_type="PTR",
                    status=RecordStatus.MISSING,
                    message=f"No PTR record for {ip_address}",
                )

            ptr_hostname = ptr_records[0].rstrip(".")

            # Verify forward DNS matches
            try:
                if isinstance(ip_obj, ipaddress.IPv4Address):
                    forward_ips = self._query(ptr_hostname, "A")
                else:
                    forward_ips = self._query(ptr_hostname, "AAAA")

                if ip_address not in forward_ips:
                    return DNSCheckResult(
                        record_type="PTR",
                        status=RecordStatus.WARNING,
                        value=ptr_hostname,
                        message=f"Forward DNS for {ptr_hostname} does not include {ip_address}",
                        details={"forward_ips": forward_ips},
                    )

            except DNSLookupError:
                return DNSCheckResult(
                    record_type="PTR",
                    status=RecordStatus.WARNING,
                    value=ptr_hostname,
                    message=f"Cannot verify forward DNS for {ptr_hostname}",
                )

            return DNSCheckResult(
                record_type="PTR",
                status=RecordStatus.VALID,
                value=ptr_hostname,
                message=f"PTR record {ptr_hostname} matches forward DNS",
            )

        except DNSLookupError as e:
            return DNSCheckResult(
                record_type="PTR",
                status=RecordStatus.MISSING,
                message=f"PTR lookup failed: {e.details.get('reason', str(e))}",
            )

    def get_server_ip(self) -> Optional[str]:
        """Get the server's external IP address."""
        try:
            # Try to get external IP using DNS
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ["208.67.222.222"]  # OpenDNS
            answers = resolver.resolve("myip.opendns.com", "A")
            return str(answers[0])
        except Exception:
            try:
                # Fallback to socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return None

    def check_all(
        self,
        domain: str,
        dkim_selectors: Optional[list[str]] = None,
        check_ptr_for_ips: Optional[list[str]] = None,
    ) -> DNSHealthReport:
        """
        Perform a complete DNS health check for a domain.

        Args:
            domain: Domain to check.
            dkim_selectors: List of DKIM selectors to check.
            check_ptr_for_ips: List of IP addresses to check PTR for.

        Returns:
            Complete DNSHealthReport.
        """
        from datetime import datetime

        report = DNSHealthReport(
            domain=domain,
            timestamp=datetime.utcnow().isoformat(),
            overall_status=RecordStatus.VALID,
            spf=self.check_spf(domain),
        )

        # Check DKIM
        if dkim_selectors:
            for selector in dkim_selectors:
                report.dkim[selector] = self.check_dkim(domain, selector)

        # Check DMARC
        report.dmarc = self.check_dmarc(domain)

        # Check MX
        report.mx = self.check_mx(domain)

        # Check PTR
        if check_ptr_for_ips:
            for ip in check_ptr_for_ips:
                report.ptr[ip] = self.check_ptr(ip)
        else:
            # Try to check PTR for server's IP
            server_ip = self.get_server_ip()
            if server_ip:
                report.ptr[server_ip] = self.check_ptr(server_ip)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        # Determine overall status
        all_results = [
            report.spf,
            report.dmarc,
            report.mx,
            *report.dkim.values(),
            *report.ptr.values(),
        ]

        if any(r.status == RecordStatus.ERROR for r in all_results):
            report.overall_status = RecordStatus.ERROR
        elif any(r.status == RecordStatus.MISSING for r in all_results):
            report.overall_status = RecordStatus.WARNING
        elif any(r.status == RecordStatus.WARNING for r in all_results):
            report.overall_status = RecordStatus.WARNING
        elif any(r.status == RecordStatus.INVALID for r in all_results):
            report.overall_status = RecordStatus.INVALID

        logger.info(
            "DNS health check for %s: %s",
            domain,
            report.overall_status.value,
        )

        return report

    def _generate_recommendations(self, report: DNSHealthReport) -> list[str]:
        """Generate recommendations based on check results."""
        recommendations = []

        # SPF recommendations
        if report.spf.status == RecordStatus.MISSING:
            recommendations.append(
                f"Add an SPF record: {report.domain} IN TXT \"v=spf1 mx -all\""
            )
        elif report.spf.status == RecordStatus.WARNING:
            if "~all" in report.spf.message:
                recommendations.append(
                    "Consider using '-all' instead of '~all' for stricter SPF enforcement"
                )

        # DKIM recommendations
        if not report.dkim:
            recommendations.append(
                "Set up DKIM signing and publish the public key in DNS"
            )
        for selector, result in report.dkim.items():
            if result.status == RecordStatus.MISSING:
                recommendations.append(
                    f"Publish DKIM record for selector '{selector}' at "
                    f"{selector}._domainkey.{report.domain}"
                )

        # DMARC recommendations
        if report.dmarc.status == RecordStatus.MISSING:
            recommendations.append(
                f"Add a DMARC record: _dmarc.{report.domain} IN TXT "
                "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{report.domain}\""
            )
        elif "none" in report.dmarc.message.lower():
            recommendations.append(
                "Upgrade DMARC policy from 'none' to 'quarantine' or 'reject'"
            )

        # MX recommendations
        if report.mx.status == RecordStatus.MISSING:
            recommendations.append(
                f"Add MX record: {report.domain} IN MX 10 mail.{report.domain}"
            )

        # PTR recommendations
        for ip, result in report.ptr.items():
            if result.status == RecordStatus.MISSING:
                recommendations.append(
                    f"Configure reverse DNS (PTR) for {ip} with your hosting provider"
                )
            elif result.status == RecordStatus.WARNING:
                recommendations.append(
                    f"Ensure PTR record for {ip} matches forward DNS"
                )

        return recommendations

    def generate_recommended_records(
        self,
        domain: str,
        mail_server: str,
        dkim_selector: str = "unitmail",
        dkim_public_key: Optional[str] = None,
        include_spf: Optional[list[str]] = None,
        dmarc_email: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Generate recommended DNS records for a domain.

        Args:
            domain: The domain name.
            mail_server: Mail server hostname.
            dkim_selector: DKIM selector name.
            dkim_public_key: Base64-encoded DKIM public key.
            include_spf: Additional SPF include domains.
            dmarc_email: Email address for DMARC reports.

        Returns:
            Dictionary of record names to values.
        """
        records = {}

        # SPF record
        spf_mechanisms = ["mx"]
        if include_spf:
            for inc in include_spf:
                spf_mechanisms.append(f"include:{inc}")
        spf_mechanisms.append("-all")
        records[f"{domain}"] = f"v=spf1 {' '.join(spf_mechanisms)}"

        # DKIM record
        if dkim_public_key:
            records[f"{dkim_selector}._domainkey.{domain}"] = (
                f"v=DKIM1; k=rsa; p={dkim_public_key}"
            )
        else:
            records[f"{dkim_selector}._domainkey.{domain}"] = (
                "v=DKIM1; k=rsa; p=<YOUR_PUBLIC_KEY_HERE>"
            )

        # DMARC record
        dmarc_email = dmarc_email or f"dmarc@{domain}"
        records[f"_dmarc.{domain}"] = (
            f"v=DMARC1; p=quarantine; pct=100; "
            f"rua=mailto:{dmarc_email}; "
            f"ruf=mailto:{dmarc_email}; "
            f"adkim=r; aspf=r"
        )

        # MX record
        records[f"{domain} (MX)"] = f"10 {mail_server}"

        return records


def create_dns_checker(
    resolver: Optional[str] = None,
    timeout: int = 5,
) -> DNSChecker:
    """
    Create a DNS checker with specified settings.

    Args:
        resolver: Custom DNS resolver address.
        timeout: Query timeout in seconds.

    Returns:
        Configured DNSChecker instance.
    """
    return DNSChecker(resolver=resolver, timeout=timeout)
