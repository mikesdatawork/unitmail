"""
DNS modules for unitMail Gateway.

This package provides DNS verification and management functionality:
- SPF, DKIM, DMARC record checking
- MX record verification
- PTR (reverse DNS) verification
- DNS health reporting and recommendations
"""

from .checker import (
    DMARCRecord,
    DNSCheckResult,
    DNSChecker,
    DNSHealthReport,
    MXRecord,
    RecordStatus,
    SPFRecord,
    create_dns_checker,
)

__all__ = [
    "DMARCRecord",
    "DNSCheckResult",
    "DNSChecker",
    "DNSHealthReport",
    "MXRecord",
    "RecordStatus",
    "SPFRecord",
    "create_dns_checker",
]
