"""
DKIM (DomainKeys Identified Mail) implementation for unitMail.

This module provides classes for signing outgoing emails with DKIM signatures
and verifying incoming DKIM signatures, ensuring email authenticity and integrity.
"""

import base64
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from email import message_from_bytes, message_from_string
from email.message import EmailMessage
from typing import Optional, Union

import dns.resolver
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from src.common.exceptions import CryptoError, DNSLookupError, SignatureError

logger = logging.getLogger(__name__)


@dataclass
class DKIMKeyPair:
    """Container for DKIM RSA key pair."""

    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    private_key_pem: bytes
    public_key_pem: bytes
    key_size: int = 2048


@dataclass
class DKIMSignature:
    """Parsed DKIM signature components."""

    version: str = "1"
    algorithm: str = "rsa-sha256"
    domain: str = ""
    selector: str = ""
    canonicalization: str = "relaxed/relaxed"
    signed_headers: list[str] = field(default_factory=list)
    body_hash: str = ""
    signature: str = ""
    timestamp: Optional[int] = None
    expiration: Optional[int] = None
    body_length: Optional[int] = None

    def to_header(self) -> str:
        """Convert signature to DKIM-Signature header value."""
        parts = [
            f"v={self.version}",
            f"a={self.algorithm}",
            f"c={self.canonicalization}",
            f"d={self.domain}",
            f"s={self.selector}",
            f"h={':'.join(self.signed_headers)}",
            f"bh={self.body_hash}",
        ]

        if self.timestamp:
            parts.append(f"t={self.timestamp}")
        if self.expiration:
            parts.append(f"x={self.expiration}")
        if self.body_length is not None:
            parts.append(f"l={self.body_length}")

        parts.append(f"b={self.signature}")

        return "; ".join(parts)


class DKIMSigner:
    """
    DKIM signer for outgoing email messages.

    This class handles generating DKIM signatures for outgoing emails,
    including key generation and management.
    """

    # Headers that should be signed (in order of preference)
    DEFAULT_SIGNED_HEADERS = [
        "from",
        "to",
        "subject",
        "date",
        "message-id",
        "content-type",
        "content-transfer-encoding",
        "mime-version",
        "reply-to",
        "cc",
        "in-reply-to",
        "references",
    ]

    def __init__(
        self,
        domain: str,
        selector: str,
        private_key: Optional[RSAPrivateKey] = None,
        private_key_pem: Optional[bytes] = None,
        private_key_path: Optional[str] = None,
        algorithm: str = "rsa-sha256",
        canonicalization: str = "relaxed/relaxed",
        signature_ttl: Optional[int] = None,
    ) -> None:
        """
        Initialize the DKIM signer.

        Args:
            domain: The signing domain (d= tag).
            selector: The DKIM selector (s= tag).
            private_key: RSA private key object.
            private_key_pem: PEM-encoded private key bytes.
            private_key_path: Path to PEM-encoded private key file.
            algorithm: Signing algorithm (rsa-sha256 or rsa-sha1).
            canonicalization: Canonicalization method (header/body).
            signature_ttl: Signature validity period in seconds.

        Raises:
            CryptoError: If no valid private key is provided.
        """
        self.domain = domain
        self.selector = selector
        self.algorithm = algorithm
        self.canonicalization = canonicalization
        self.signature_ttl = signature_ttl

        # Load private key from various sources
        self._private_key = self._load_private_key(
            private_key, private_key_pem, private_key_path
        )

        logger.info(
            "Initialized DKIM signer for domain=%s, selector=%s",
            domain,
            selector,
        )

    def _load_private_key(
        self,
        private_key: Optional[RSAPrivateKey],
        private_key_pem: Optional[bytes],
        private_key_path: Optional[str],
    ) -> RSAPrivateKey:
        """Load private key from provided source."""
        if private_key:
            return private_key

        if private_key_pem:
            try:
                return serialization.load_pem_private_key(
                    private_key_pem,
                    password=None,
                    backend=default_backend(),
                )
            except Exception as e:
                raise CryptoError(f"Failed to load private key from PEM: {e}")

        if private_key_path:
            try:
                with open(private_key_path, "rb") as f:
                    return serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend(),
                    )
            except Exception as e:
                raise CryptoError(f"Failed to load private key from file: {e}")

        raise CryptoError("No private key provided for DKIM signing")

    @staticmethod
    def generate_key_pair(key_size: int = 2048) -> DKIMKeyPair:
        """
        Generate a new RSA key pair for DKIM signing.

        Args:
            key_size: RSA key size in bits (2048 recommended minimum).

        Returns:
            DKIMKeyPair containing the generated keys.

        Raises:
            CryptoError: If key generation fails.
        """
        if key_size < 1024:
            raise CryptoError("Key size must be at least 1024 bits")
        if key_size < 2048:
            logger.warning("Key size less than 2048 bits is not recommended")

        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend(),
            )
            public_key = private_key.public_key()

            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )

            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            logger.info("Generated new DKIM key pair with %d-bit RSA", key_size)

            return DKIMKeyPair(
                private_key=private_key,
                public_key=public_key,
                private_key_pem=private_key_pem,
                public_key_pem=public_key_pem,
                key_size=key_size,
            )

        except Exception as e:
            raise CryptoError(f"Failed to generate DKIM key pair: {e}")

    @staticmethod
    def generate_dns_record(public_key_pem: bytes, selector: str) -> str:
        """
        Generate a DNS TXT record for publishing the DKIM public key.

        Args:
            public_key_pem: PEM-encoded public key.
            selector: DKIM selector.

        Returns:
            DNS TXT record value for the DKIM public key.
        """
        # Extract the base64 key data from PEM
        pem_str = public_key_pem.decode("utf-8")
        lines = pem_str.strip().split("\n")
        # Remove header and footer lines
        key_data = "".join(
            line for line in lines
            if not line.startswith("-----")
        )

        # Format as DKIM DNS record
        record = f"v=DKIM1; k=rsa; p={key_data}"

        return record

    def _canonicalize_header(self, name: str, value: str, method: str) -> str:
        """Canonicalize a header according to DKIM specification."""
        if method == "relaxed":
            # Convert header name to lowercase
            name = name.lower()
            # Unfold header value (remove CRLF followed by whitespace)
            value = re.sub(r"\r\n[ \t]+", " ", value)
            # Convert sequences of whitespace to single space
            value = re.sub(r"[ \t]+", " ", value)
            # Strip leading/trailing whitespace
            value = value.strip()
            return f"{name}:{value}"
        else:
            # Simple canonicalization - preserve as-is
            return f"{name}:{value}"

    def _canonicalize_body(self, body: bytes, method: str) -> bytes:
        """Canonicalize the message body according to DKIM specification."""
        if method == "relaxed":
            # Convert to string for processing
            body_str = body.decode("utf-8", errors="replace")
            lines = body_str.split("\n")
            result_lines = []

            for line in lines:
                # Remove trailing whitespace from each line
                line = line.rstrip(" \t\r")
                # Reduce sequences of whitespace to single space
                line = re.sub(r"[ \t]+", " ", line)
                result_lines.append(line)

            # Join with CRLF
            result = "\r\n".join(result_lines)
            # Remove trailing empty lines (but keep one CRLF)
            result = result.rstrip("\r\n") + "\r\n"

            return result.encode("utf-8")
        else:
            # Simple canonicalization - just ensure CRLF line endings
            # and remove trailing empty lines
            body = body.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            while body.endswith(b"\r\n\r\n"):
                body = body[:-2]
            if not body.endswith(b"\r\n"):
                body += b"\r\n"
            return body

    def _compute_body_hash(self, body: bytes, method: str) -> str:
        """Compute the hash of the canonicalized body."""
        canonical_body = self._canonicalize_body(body, method)

        if self.algorithm == "rsa-sha256":
            hash_obj = hashlib.sha256(canonical_body)
        else:
            hash_obj = hashlib.sha1(canonical_body)

        return base64.b64encode(hash_obj.digest()).decode("ascii")

    def sign(
        self,
        message: Union[bytes, str, EmailMessage],
        signed_headers: Optional[list[str]] = None,
    ) -> str:
        """
        Sign an email message with DKIM.

        Args:
            message: Email message (bytes, string, or EmailMessage).
            signed_headers: List of headers to sign (uses defaults if None).

        Returns:
            The complete DKIM-Signature header line.

        Raises:
            CryptoError: If signing fails.
        """
        try:
            # Parse message if needed
            if isinstance(message, bytes):
                msg = message_from_bytes(message)
                raw_message = message
            elif isinstance(message, str):
                msg = message_from_string(message)
                raw_message = message.encode("utf-8")
            else:
                msg = message
                raw_message = message.as_bytes()

            # Split headers and body
            raw_str = raw_message.decode("utf-8", errors="replace")
            if "\r\n\r\n" in raw_str:
                _, body_str = raw_str.split("\r\n\r\n", 1)
            elif "\n\n" in raw_str:
                _, body_str = raw_str.split("\n\n", 1)
            else:
                body_str = ""
            body = body_str.encode("utf-8")

            # Determine headers to sign
            if signed_headers is None:
                signed_headers = [
                    h.lower() for h in self.DEFAULT_SIGNED_HEADERS
                    if h.lower() in [k.lower() for k in msg.keys()]
                ]
            else:
                signed_headers = [h.lower() for h in signed_headers]

            # Ensure 'from' is always signed
            if "from" not in signed_headers:
                signed_headers.insert(0, "from")

            # Parse canonicalization methods
            if "/" in self.canonicalization:
                header_canon, body_canon = self.canonicalization.split("/")
            else:
                header_canon = body_canon = self.canonicalization

            # Compute body hash
            body_hash = self._compute_body_hash(body, body_canon)

            # Build signature structure
            sig = DKIMSignature(
                algorithm=self.algorithm,
                domain=self.domain,
                selector=self.selector,
                canonicalization=self.canonicalization,
                signed_headers=signed_headers,
                body_hash=body_hash,
                timestamp=int(time.time()),
            )

            if self.signature_ttl:
                sig.expiration = sig.timestamp + self.signature_ttl

            # Build header string to sign (without b= value)
            sig_header_value = sig.to_header().replace(f"b={sig.signature}", "b=")

            # Canonicalize headers
            headers_to_sign = []
            for header_name in signed_headers:
                for key in msg.keys():
                    if key.lower() == header_name:
                        value = msg[key]
                        headers_to_sign.append(
                            self._canonicalize_header(key, value, header_canon)
                        )
                        break

            # Add DKIM-Signature header (without trailing CRLF)
            dkim_header = self._canonicalize_header(
                "dkim-signature", sig_header_value, header_canon
            )
            headers_to_sign.append(dkim_header)

            # Create data to sign
            data_to_sign = "\r\n".join(headers_to_sign).encode("utf-8")

            # Sign with RSA
            if self.algorithm == "rsa-sha256":
                hash_alg = hashes.SHA256()
            else:
                hash_alg = hashes.SHA1()

            signature = self._private_key.sign(
                data_to_sign,
                padding.PKCS1v15(),
                hash_alg,
            )

            sig.signature = base64.b64encode(signature).decode("ascii")

            # Format final header
            header_line = f"DKIM-Signature: {sig.to_header()}"

            logger.debug(
                "Generated DKIM signature for domain=%s, selector=%s",
                self.domain,
                self.selector,
            )

            return header_line

        except CryptoError:
            raise
        except Exception as e:
            raise CryptoError(f"Failed to sign message with DKIM: {e}")

    def sign_message(
        self,
        message: Union[bytes, str, EmailMessage],
        signed_headers: Optional[list[str]] = None,
    ) -> bytes:
        """
        Sign a message and prepend the DKIM-Signature header.

        Args:
            message: Email message to sign.
            signed_headers: List of headers to sign.

        Returns:
            The signed message with DKIM-Signature header prepended.
        """
        if isinstance(message, bytes):
            raw_message = message
        elif isinstance(message, str):
            raw_message = message.encode("utf-8")
        else:
            raw_message = message.as_bytes()

        signature_header = self.sign(message, signed_headers)

        # Prepend signature header to message
        return f"{signature_header}\r\n".encode("utf-8") + raw_message


class DKIMVerifier:
    """
    DKIM signature verifier for incoming email messages.

    This class verifies DKIM signatures on incoming emails by
    fetching public keys from DNS and validating signatures.
    """

    def __init__(
        self,
        dns_resolver: Optional[str] = None,
        dns_timeout: int = 5,
    ) -> None:
        """
        Initialize the DKIM verifier.

        Args:
            dns_resolver: Custom DNS resolver address.
            dns_timeout: DNS query timeout in seconds.
        """
        self.dns_timeout = dns_timeout

        self._resolver = dns.resolver.Resolver()
        if dns_resolver:
            self._resolver.nameservers = [dns_resolver]
        self._resolver.lifetime = dns_timeout

        logger.info("Initialized DKIM verifier")

    @staticmethod
    def parse_signature(header_value: str) -> DKIMSignature:
        """
        Parse a DKIM-Signature header value.

        Args:
            header_value: The value of the DKIM-Signature header.

        Returns:
            Parsed DKIMSignature object.

        Raises:
            SignatureError: If the signature is malformed.
        """
        sig = DKIMSignature()

        # Parse tag=value pairs
        # Handle both semicolon and whitespace separation
        parts = re.split(r";\s*", header_value.strip())

        for part in parts:
            if "=" not in part:
                continue
            tag, value = part.split("=", 1)
            tag = tag.strip().lower()
            value = value.strip()

            if tag == "v":
                sig.version = value
            elif tag == "a":
                sig.algorithm = value
            elif tag == "c":
                sig.canonicalization = value
            elif tag == "d":
                sig.domain = value
            elif tag == "s":
                sig.selector = value
            elif tag == "h":
                sig.signed_headers = [h.strip().lower() for h in value.split(":")]
            elif tag == "bh":
                sig.body_hash = value.replace(" ", "").replace("\t", "")
            elif tag == "b":
                sig.signature = value.replace(" ", "").replace("\t", "")
            elif tag == "t":
                sig.timestamp = int(value)
            elif tag == "x":
                sig.expiration = int(value)
            elif tag == "l":
                sig.body_length = int(value)

        # Validate required fields
        if not sig.domain:
            raise SignatureError("Missing domain (d=) in DKIM signature")
        if not sig.selector:
            raise SignatureError("Missing selector (s=) in DKIM signature")
        if not sig.signature:
            raise SignatureError("Missing signature (b=) in DKIM signature")
        if not sig.body_hash:
            raise SignatureError("Missing body hash (bh=) in DKIM signature")
        if not sig.signed_headers:
            raise SignatureError("Missing signed headers (h=) in DKIM signature")
        if "from" not in sig.signed_headers:
            raise SignatureError("'From' header must be signed")

        return sig

    def _fetch_public_key(self, domain: str, selector: str) -> RSAPublicKey:
        """
        Fetch the DKIM public key from DNS.

        Args:
            domain: The signing domain.
            selector: The DKIM selector.

        Returns:
            The RSA public key.

        Raises:
            DNSLookupError: If DNS lookup fails.
            SignatureError: If the key is invalid or not found.
        """
        dkim_domain = f"{selector}._domainkey.{domain}"

        try:
            answers = self._resolver.resolve(dkim_domain, "TXT")
        except dns.resolver.NXDOMAIN:
            raise DNSLookupError(dkim_domain, "TXT", {"reason": "Domain not found"})
        except dns.resolver.NoAnswer:
            raise DNSLookupError(dkim_domain, "TXT", {"reason": "No TXT record"})
        except dns.resolver.Timeout:
            raise DNSLookupError(dkim_domain, "TXT", {"reason": "Timeout"})
        except Exception as e:
            raise DNSLookupError(dkim_domain, "TXT", {"reason": str(e)})

        # Concatenate all TXT record parts
        txt_data = ""
        for rdata in answers:
            for txt_string in rdata.strings:
                txt_data += txt_string.decode("utf-8", errors="replace")

        # Parse the DKIM record
        key_data = None
        for part in txt_data.split(";"):
            part = part.strip()
            if part.startswith("p="):
                key_data = part[2:].replace(" ", "")
                break

        if not key_data:
            raise SignatureError(f"No public key (p=) in DKIM record for {dkim_domain}")

        if key_data == "":
            raise SignatureError(f"DKIM key revoked for {dkim_domain}")

        # Decode and load the public key
        try:
            key_bytes = base64.b64decode(key_data)
            public_key = serialization.load_der_public_key(
                key_bytes,
                backend=default_backend(),
            )
            return public_key
        except Exception as e:
            raise SignatureError(f"Failed to parse DKIM public key: {e}")

    def _canonicalize_header(self, name: str, value: str, method: str) -> str:
        """Canonicalize a header according to DKIM specification."""
        if method == "relaxed":
            name = name.lower()
            value = re.sub(r"\r\n[ \t]+", " ", value)
            value = re.sub(r"[ \t]+", " ", value)
            value = value.strip()
            return f"{name}:{value}"
        else:
            return f"{name}:{value}"

    def _canonicalize_body(self, body: bytes, method: str) -> bytes:
        """Canonicalize the message body according to DKIM specification."""
        if method == "relaxed":
            body_str = body.decode("utf-8", errors="replace")
            lines = body_str.split("\n")
            result_lines = []

            for line in lines:
                line = line.rstrip(" \t\r")
                line = re.sub(r"[ \t]+", " ", line)
                result_lines.append(line)

            result = "\r\n".join(result_lines)
            result = result.rstrip("\r\n") + "\r\n"

            return result.encode("utf-8")
        else:
            body = body.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            while body.endswith(b"\r\n\r\n"):
                body = body[:-2]
            if not body.endswith(b"\r\n"):
                body += b"\r\n"
            return body

    def verify(self, message: Union[bytes, str]) -> tuple[bool, str]:
        """
        Verify the DKIM signature of an email message.

        Args:
            message: The email message to verify.

        Returns:
            Tuple of (is_valid, result_description).
        """
        try:
            # Parse message
            if isinstance(message, bytes):
                msg = message_from_bytes(message)
                raw_message = message
            else:
                msg = message_from_string(message)
                raw_message = message.encode("utf-8")

            # Get DKIM-Signature header
            dkim_header = msg.get("DKIM-Signature")
            if not dkim_header:
                return False, "No DKIM-Signature header found"

            # Parse signature
            try:
                sig = self.parse_signature(dkim_header)
            except SignatureError as e:
                return False, f"Invalid signature format: {e}"

            # Check expiration
            if sig.expiration:
                if time.time() > sig.expiration:
                    return False, "Signature has expired"

            # Fetch public key
            try:
                public_key = self._fetch_public_key(sig.domain, sig.selector)
            except (DNSLookupError, SignatureError) as e:
                return False, f"Failed to fetch public key: {e}"

            # Parse canonicalization methods
            if "/" in sig.canonicalization:
                header_canon, body_canon = sig.canonicalization.split("/")
            else:
                header_canon = body_canon = sig.canonicalization

            # Extract body
            raw_str = raw_message.decode("utf-8", errors="replace")
            if "\r\n\r\n" in raw_str:
                _, body_str = raw_str.split("\r\n\r\n", 1)
            elif "\n\n" in raw_str:
                _, body_str = raw_str.split("\n\n", 1)
            else:
                body_str = ""
            body = body_str.encode("utf-8")

            # Apply body length limit if specified
            if sig.body_length is not None:
                body = body[:sig.body_length]

            # Verify body hash
            canonical_body = self._canonicalize_body(body, body_canon)
            if sig.algorithm == "rsa-sha256":
                body_hash = base64.b64encode(
                    hashlib.sha256(canonical_body).digest()
                ).decode("ascii")
            else:
                body_hash = base64.b64encode(
                    hashlib.sha1(canonical_body).digest()
                ).decode("ascii")

            if body_hash != sig.body_hash:
                return False, "Body hash mismatch"

            # Build headers to verify
            headers_to_sign = []
            for header_name in sig.signed_headers:
                for key in msg.keys():
                    if key.lower() == header_name:
                        value = msg[key]
                        headers_to_sign.append(
                            self._canonicalize_header(key, value, header_canon)
                        )
                        break

            # Add DKIM-Signature header without the b= value
            dkim_value = re.sub(
                r"b=[^;]*",
                "b=",
                dkim_header,
                flags=re.IGNORECASE,
            )
            dkim_header_canon = self._canonicalize_header(
                "dkim-signature", dkim_value, header_canon
            )
            headers_to_sign.append(dkim_header_canon)

            # Create data to verify
            data_to_verify = "\r\n".join(headers_to_sign).encode("utf-8")

            # Decode signature
            try:
                signature_bytes = base64.b64decode(sig.signature)
            except Exception:
                return False, "Invalid signature encoding"

            # Verify signature
            try:
                if sig.algorithm == "rsa-sha256":
                    hash_alg = hashes.SHA256()
                else:
                    hash_alg = hashes.SHA1()

                public_key.verify(
                    signature_bytes,
                    data_to_verify,
                    padding.PKCS1v15(),
                    hash_alg,
                )

                logger.info(
                    "DKIM signature verified for domain=%s, selector=%s",
                    sig.domain,
                    sig.selector,
                )

                return True, f"Valid signature from {sig.domain}"

            except Exception as e:
                logger.warning(
                    "DKIM signature verification failed: %s", str(e)
                )
                return False, "Signature verification failed"

        except Exception as e:
            logger.error("DKIM verification error: %s", str(e))
            return False, f"Verification error: {e}"


def generate_dkim_keys(
    domain: str,
    selector: str,
    key_size: int = 2048,
    output_dir: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Generate DKIM keys and DNS record for a domain.

    Args:
        domain: The domain for DKIM signing.
        selector: The DKIM selector.
        key_size: RSA key size in bits.
        output_dir: Directory to save key files (optional).

    Returns:
        Tuple of (private_key_pem, public_key_pem, dns_record).
    """
    key_pair = DKIMSigner.generate_key_pair(key_size)
    dns_record = DKIMSigner.generate_dns_record(key_pair.public_key_pem, selector)

    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)

        private_key_path = os.path.join(output_dir, f"{selector}.{domain}.private.pem")
        public_key_path = os.path.join(output_dir, f"{selector}.{domain}.public.pem")
        dns_record_path = os.path.join(output_dir, f"{selector}.{domain}.dns.txt")

        with open(private_key_path, "wb") as f:
            f.write(key_pair.private_key_pem)
        with open(public_key_path, "wb") as f:
            f.write(key_pair.public_key_pem)
        with open(dns_record_path, "w") as f:
            f.write(f"{selector}._domainkey.{domain} IN TXT \"{dns_record}\"\n")

        logger.info("Saved DKIM keys to %s", output_dir)

    return (
        key_pair.private_key_pem.decode("utf-8"),
        key_pair.public_key_pem.decode("utf-8"),
        dns_record,
    )
