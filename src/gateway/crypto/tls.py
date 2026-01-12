"""
TLS (Transport Layer Security) configuration and management for unitMail.

This module provides TLS configuration, certificate management, and
context creation for secure SMTP and HTTP communications.
"""

import logging
import os
import ssl
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from src.common.exceptions import ConfigurationError, CryptoError

logger = logging.getLogger(__name__)


class TLSVersion(Enum):
    """Supported TLS versions."""

    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class CertificateType(Enum):
    """Types of certificates."""

    SELF_SIGNED = "self_signed"
    LETS_ENCRYPT = "lets_encrypt"
    CUSTOM = "custom"


@dataclass
class CertificateInfo:
    """Information about an X.509 certificate."""

    subject: str
    issuer: str
    serial_number: int
    not_before: datetime
    not_after: datetime
    is_expired: bool
    days_until_expiry: int
    san_domains: list[str] = field(default_factory=list)
    key_type: str = ""
    key_size: int = 0
    signature_algorithm: str = ""
    is_self_signed: bool = False

    def is_valid(self) -> bool:
        """Check if the certificate is currently valid."""
        now = datetime.now(timezone.utc)
        return self.not_before <= now <= self.not_after


# Modern cipher suites for TLS 1.2+
# Prioritizes ECDHE and forward secrecy
TLS_1_2_CIPHERS = [
    "ECDHE-ECDSA-AES256-GCM-SHA384",
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-CHACHA20-POLY1305",
    "ECDHE-RSA-CHACHA20-POLY1305",
    "ECDHE-ECDSA-AES128-GCM-SHA256",
    "ECDHE-RSA-AES128-GCM-SHA256",
    "DHE-RSA-AES256-GCM-SHA384",
    "DHE-RSA-AES128-GCM-SHA256",
]

# TLS 1.3 cipher suites (these are mandatory in TLS 1.3)
TLS_1_3_CIPHERS = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_GCM_SHA256",
]


@dataclass
class TLSConfig:
    """
    TLS configuration settings.

    This class holds all TLS-related configuration options for
    secure connections in SMTP and HTTP contexts.
    """

    # Certificate paths
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    ca_path: Optional[str] = None

    # TLS version settings
    min_version: TLSVersion = TLSVersion.TLS_1_2
    max_version: TLSVersion = TLSVersion.TLS_1_3

    # Cipher configuration
    ciphers: list[str] = field(default_factory=lambda: TLS_1_2_CIPHERS.copy())
    ciphersuites: list[str] = field(default_factory=lambda: TLS_1_3_CIPHERS.copy())

    # Verification settings
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED
    check_hostname: bool = True

    # OCSP stapling
    ocsp_stapling: bool = True

    # Session settings
    session_cache_mode: int = ssl.SESS_CACHE_SERVER
    session_timeout: int = 300

    # ALPN protocols
    alpn_protocols: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])

    # SNI callback
    sni_callback: Optional[callable] = None

    def get_cipher_string(self) -> str:
        """Get the cipher string for TLS 1.2."""
        return ":".join(self.ciphers)

    def get_ciphersuites_string(self) -> str:
        """Get the ciphersuites string for TLS 1.3."""
        return ":".join(self.ciphersuites)


class CertificateManager:
    """
    Manager for TLS certificates.

    Handles loading, validation, and generation of certificates
    for secure communications.
    """

    def __init__(self, cert_dir: Optional[str] = None) -> None:
        """
        Initialize the certificate manager.

        Args:
            cert_dir: Base directory for certificate storage.
        """
        self.cert_dir = Path(cert_dir) if cert_dir else None
        if self.cert_dir:
            self.cert_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Initialized certificate manager")

    def load_certificate(self, cert_path: str) -> x509.Certificate:
        """
        Load an X.509 certificate from file.

        Args:
            cert_path: Path to the certificate file (PEM format).

        Returns:
            Loaded certificate object.

        Raises:
            CryptoError: If loading fails.
        """
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            logger.debug("Loaded certificate from %s", cert_path)
            return cert

        except Exception as e:
            raise CryptoError(f"Failed to load certificate from {cert_path}: {e}")

    def load_private_key(
        self,
        key_path: str,
        password: Optional[bytes] = None,
    ) -> Union[RSAPrivateKey, EllipticCurvePrivateKey]:
        """
        Load a private key from file.

        Args:
            key_path: Path to the private key file (PEM format).
            password: Optional password for encrypted keys.

        Returns:
            Loaded private key object.

        Raises:
            CryptoError: If loading fails.
        """
        try:
            with open(key_path, "rb") as f:
                key_data = f.read()

            private_key = serialization.load_pem_private_key(
                key_data,
                password=password,
                backend=default_backend(),
            )
            logger.debug("Loaded private key from %s", key_path)
            return private_key

        except Exception as e:
            raise CryptoError(f"Failed to load private key from {key_path}: {e}")

    def get_certificate_info(
        self,
        cert: Union[x509.Certificate, str],
    ) -> CertificateInfo:
        """
        Get information about a certificate.

        Args:
            cert: Certificate object or path to certificate file.

        Returns:
            CertificateInfo with certificate details.
        """
        if isinstance(cert, str):
            cert = self.load_certificate(cert)

        now = datetime.now(timezone.utc)
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc

        # Extract subject and issuer
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()

        # Check if self-signed
        is_self_signed = cert.subject == cert.issuer

        # Get SAN domains
        san_domains = []
        try:
            san_ext = cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            )
            for name in san_ext.value:
                if isinstance(name, x509.DNSName):
                    san_domains.append(name.value)
        except x509.ExtensionNotFound:
            pass

        # Get key info
        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            key_type = "RSA"
            key_size = public_key.key_size
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            key_type = f"EC ({public_key.curve.name})"
            key_size = public_key.curve.key_size
        else:
            key_type = "Unknown"
            key_size = 0

        # Get signature algorithm
        sig_alg = cert.signature_algorithm_oid._name

        days_until_expiry = (not_after - now).days

        return CertificateInfo(
            subject=subject,
            issuer=issuer,
            serial_number=cert.serial_number,
            not_before=not_before,
            not_after=not_after,
            is_expired=now > not_after,
            days_until_expiry=days_until_expiry,
            san_domains=san_domains,
            key_type=key_type,
            key_size=key_size,
            signature_algorithm=sig_alg,
            is_self_signed=is_self_signed,
        )

    def validate_certificate(
        self,
        cert_path: str,
        key_path: Optional[str] = None,
        check_expiry_days: int = 30,
    ) -> tuple[bool, list[str]]:
        """
        Validate a certificate and optionally its private key.

        Args:
            cert_path: Path to the certificate file.
            key_path: Optional path to the private key file.
            check_expiry_days: Warn if certificate expires within this many days.

        Returns:
            Tuple of (is_valid, list of issues).
        """
        issues = []

        try:
            cert = self.load_certificate(cert_path)
            info = self.get_certificate_info(cert)

            if info.is_expired:
                issues.append(f"Certificate expired on {info.not_after}")

            if info.days_until_expiry <= check_expiry_days:
                issues.append(
                    f"Certificate expires in {info.days_until_expiry} days"
                )

            if info.is_self_signed:
                issues.append("Certificate is self-signed")

            if key_path:
                try:
                    private_key = self.load_private_key(key_path)

                    # Verify key matches certificate
                    cert_public_key = cert.public_key()

                    if isinstance(private_key, rsa.RSAPrivateKey):
                        if not isinstance(cert_public_key, rsa.RSAPublicKey):
                            issues.append("Private key type does not match certificate")
                        elif (
                            private_key.public_key().public_numbers()
                            != cert_public_key.public_numbers()
                        ):
                            issues.append("Private key does not match certificate")

                    elif isinstance(private_key, ec.EllipticCurvePrivateKey):
                        if not isinstance(cert_public_key, ec.EllipticCurvePublicKey):
                            issues.append("Private key type does not match certificate")
                        elif (
                            private_key.public_key().public_numbers()
                            != cert_public_key.public_numbers()
                        ):
                            issues.append("Private key does not match certificate")

                except CryptoError as e:
                    issues.append(f"Failed to load private key: {e}")

        except CryptoError as e:
            issues.append(f"Failed to load certificate: {e}")

        is_valid = len([i for i in issues if "expires in" not in i.lower()]) == 0
        return is_valid, issues

    def generate_self_signed_certificate(
        self,
        common_name: str,
        domains: Optional[list[str]] = None,
        organization: str = "unitMail",
        country: str = "US",
        validity_days: int = 365,
        key_size: int = 2048,
        key_type: str = "rsa",
        output_dir: Optional[str] = None,
    ) -> tuple[bytes, bytes]:
        """
        Generate a self-signed certificate.

        Args:
            common_name: Certificate common name (CN).
            domains: Additional domain names for SAN.
            organization: Organization name.
            country: Country code.
            validity_days: Certificate validity in days.
            key_size: RSA key size or EC curve size.
            key_type: Key type ("rsa" or "ec").
            output_dir: Directory to save certificate files.

        Returns:
            Tuple of (certificate_pem, private_key_pem).
        """
        # Generate private key
        if key_type == "ec":
            private_key = ec.generate_private_key(
                ec.SECP256R1(),
                default_backend(),
            )
        else:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend(),
            )

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build SAN extension
        san_names = [x509.DNSName(common_name)]
        if domains:
            for domain in domains:
                if domain != common_name:
                    san_names.append(x509.DNSName(domain))

        # Build certificate
        now = datetime.now(timezone.utc)
        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)  # Self-signed
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(
                x509.SubjectAlternativeName(san_names),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            )
        )

        # Sign certificate
        certificate = cert_builder.sign(private_key, hashes.SHA256(), default_backend())

        # Serialize to PEM
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Save to files if output_dir specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            cert_file = output_path / f"{common_name}.crt"
            key_file = output_path / f"{common_name}.key"

            with open(cert_file, "wb") as f:
                f.write(cert_pem)
            with open(key_file, "wb") as f:
                f.write(key_pem)

            # Set restrictive permissions on key file
            os.chmod(key_file, 0o600)

            logger.info(
                "Generated self-signed certificate for %s in %s",
                common_name,
                output_dir,
            )

        return cert_pem, key_pem


class LetsEncryptHelper:
    """
    Helper for Let's Encrypt certificate management.

    Provides utilities for obtaining and renewing certificates
    using the ACME protocol via certbot.
    """

    CERTBOT_LIVE_DIR = "/etc/letsencrypt/live"
    CERTBOT_RENEWAL_DIR = "/etc/letsencrypt/renewal"

    def __init__(
        self,
        webroot: Optional[str] = None,
        email: Optional[str] = None,
        staging: bool = False,
    ) -> None:
        """
        Initialize Let's Encrypt helper.

        Args:
            webroot: Webroot directory for HTTP-01 challenge.
            email: Email for Let's Encrypt registration.
            staging: Use staging server for testing.
        """
        self.webroot = webroot
        self.email = email
        self.staging = staging

        logger.info("Initialized Let's Encrypt helper")

    def check_certbot_installed(self) -> bool:
        """Check if certbot is installed and accessible."""
        try:
            result = subprocess.run(
                ["certbot", "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_certificate_paths(self, domain: str) -> tuple[str, str, str]:
        """
        Get paths to Let's Encrypt certificate files for a domain.

        Args:
            domain: The domain name.

        Returns:
            Tuple of (cert_path, key_path, chain_path).
        """
        live_dir = Path(self.CERTBOT_LIVE_DIR) / domain

        return (
            str(live_dir / "fullchain.pem"),
            str(live_dir / "privkey.pem"),
            str(live_dir / "chain.pem"),
        )

    def certificate_exists(self, domain: str) -> bool:
        """Check if a Let's Encrypt certificate exists for a domain."""
        cert_path, key_path, _ = self.get_certificate_paths(domain)
        return Path(cert_path).exists() and Path(key_path).exists()

    def request_certificate(
        self,
        domains: list[str],
        webroot: Optional[str] = None,
        standalone: bool = False,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Request a new certificate from Let's Encrypt.

        Args:
            domains: List of domain names.
            webroot: Override webroot directory.
            standalone: Use standalone mode instead of webroot.
            dry_run: Perform a dry run without obtaining certificate.

        Returns:
            Tuple of (success, message).
        """
        if not self.check_certbot_installed():
            return False, "certbot is not installed"

        cmd = ["certbot", "certonly"]

        if self.staging:
            cmd.append("--staging")

        if dry_run:
            cmd.append("--dry-run")

        if standalone:
            cmd.append("--standalone")
        else:
            webroot_dir = webroot or self.webroot
            if not webroot_dir:
                return False, "Webroot directory not specified"
            cmd.extend(["--webroot", "-w", webroot_dir])

        if self.email:
            cmd.extend(["--email", self.email])
        else:
            cmd.append("--register-unsafely-without-email")

        cmd.append("--agree-tos")
        cmd.append("--non-interactive")

        for domain in domains:
            cmd.extend(["-d", domain])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(
                    "Successfully obtained Let's Encrypt certificate for %s",
                    ", ".join(domains),
                )
                return True, "Certificate obtained successfully"
            else:
                error_msg = result.stderr or result.stdout
                logger.error(
                    "Failed to obtain Let's Encrypt certificate: %s",
                    error_msg,
                )
                return False, f"Failed to obtain certificate: {error_msg}"

        except Exception as e:
            logger.error("Error running certbot: %s", str(e))
            return False, f"Error running certbot: {e}"

    def renew_certificates(self, force: bool = False) -> tuple[bool, str]:
        """
        Renew all Let's Encrypt certificates.

        Args:
            force: Force renewal even if not due.

        Returns:
            Tuple of (success, message).
        """
        if not self.check_certbot_installed():
            return False, "certbot is not installed"

        cmd = ["certbot", "renew"]

        if force:
            cmd.append("--force-renewal")

        cmd.append("--non-interactive")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("Certificate renewal completed")
                return True, "Renewal completed successfully"
            else:
                error_msg = result.stderr or result.stdout
                logger.error("Certificate renewal failed: %s", error_msg)
                return False, f"Renewal failed: {error_msg}"

        except Exception as e:
            logger.error("Error running certbot renew: %s", str(e))
            return False, f"Error running certbot: {e}"

    def get_renewal_info(self, domain: str) -> Optional[dict]:
        """
        Get renewal information for a domain's certificate.

        Args:
            domain: The domain name.

        Returns:
            Dictionary with renewal info or None if not found.
        """
        renewal_conf = Path(self.CERTBOT_RENEWAL_DIR) / f"{domain}.conf"

        if not renewal_conf.exists():
            return None

        try:
            with open(renewal_conf, "r") as f:
                content = f.read()

            info = {"domain": domain}

            # Parse key=value lines
            for line in content.split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    info[key.strip()] = value.strip()

            return info

        except Exception as e:
            logger.warning(
                "Failed to read renewal config for %s: %s",
                domain,
                str(e),
            )
            return None


class TLSContextFactory:
    """
    Factory for creating SSL/TLS contexts.

    Provides methods to create properly configured SSL contexts
    for various use cases (SMTP server, SMTP client, HTTP).
    """

    def __init__(self, config: Optional[TLSConfig] = None) -> None:
        """
        Initialize the TLS context factory.

        Args:
            config: TLS configuration settings.
        """
        self.config = config or TLSConfig()
        logger.info("Initialized TLS context factory")

    def create_server_context(
        self,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        purpose: str = "smtp",
    ) -> ssl.SSLContext:
        """
        Create an SSL context for server use.

        Args:
            cert_file: Path to certificate file.
            key_file: Path to private key file.
            purpose: Context purpose ("smtp" or "http").

        Returns:
            Configured SSLContext for server use.

        Raises:
            ConfigurationError: If certificate files are not provided.
        """
        cert_file = cert_file or self.config.cert_file
        key_file = key_file or self.config.key_file

        if not cert_file or not key_file:
            raise ConfigurationError(
                "Certificate and key files are required for server context"
            )

        # Create context with appropriate protocol
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        # Set minimum TLS version
        if self.config.min_version == TLSVersion.TLS_1_2:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        elif self.config.min_version == TLSVersion.TLS_1_3:
            context.minimum_version = ssl.TLSVersion.TLSv1_3

        # Set maximum TLS version
        if self.config.max_version == TLSVersion.TLS_1_2:
            context.maximum_version = ssl.TLSVersion.TLSv1_2
        elif self.config.max_version == TLSVersion.TLS_1_3:
            context.maximum_version = ssl.TLSVersion.TLSv1_3

        # Load certificate and key
        try:
            context.load_cert_chain(cert_file, key_file)
        except Exception as e:
            raise ConfigurationError(f"Failed to load certificate chain: {e}")

        # Load CA certificates if specified
        if self.config.ca_file or self.config.ca_path:
            try:
                context.load_verify_locations(
                    cafile=self.config.ca_file,
                    capath=self.config.ca_path,
                )
            except Exception as e:
                logger.warning("Failed to load CA certificates: %s", str(e))

        # Set cipher suites
        try:
            context.set_ciphers(self.config.get_cipher_string())
        except ssl.SSLError as e:
            logger.warning("Failed to set custom ciphers: %s", str(e))

        # Set TLS 1.3 ciphersuites if supported
        if hasattr(context, "set_ciphersuites"):
            try:
                context.set_ciphersuites(self.config.get_ciphersuites_string())
            except ssl.SSLError as e:
                logger.warning("Failed to set TLS 1.3 ciphersuites: %s", str(e))

        # Disable compression (CRIME attack mitigation)
        context.options |= ssl.OP_NO_COMPRESSION

        # Enable session tickets
        context.options |= ssl.OP_NO_TICKET  # Disable for forward secrecy

        # Set session cache mode
        context.set_session_cache_mode(self.config.session_cache_mode)

        # Set ALPN protocols for HTTP/2 support
        if purpose == "http" and self.config.alpn_protocols:
            context.set_alpn_protocols(self.config.alpn_protocols)

        # Set SNI callback if provided
        if self.config.sni_callback:
            context.sni_callback = self.config.sni_callback

        logger.debug(
            "Created server SSL context for %s with TLS %s-%s",
            purpose,
            self.config.min_version.value,
            self.config.max_version.value,
        )

        return context

    def create_client_context(
        self,
        verify: bool = True,
        check_hostname: bool = True,
    ) -> ssl.SSLContext:
        """
        Create an SSL context for client use.

        Args:
            verify: Whether to verify server certificate.
            check_hostname: Whether to check hostname.

        Returns:
            Configured SSLContext for client use.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Set minimum TLS version
        if self.config.min_version == TLSVersion.TLS_1_2:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        elif self.config.min_version == TLSVersion.TLS_1_3:
            context.minimum_version = ssl.TLSVersion.TLSv1_3

        # Configure verification
        if verify:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = check_hostname
            context.load_default_certs()
        else:
            context.verify_mode = ssl.CERT_NONE
            context.check_hostname = False

        # Load custom CA if specified
        if self.config.ca_file or self.config.ca_path:
            try:
                context.load_verify_locations(
                    cafile=self.config.ca_file,
                    capath=self.config.ca_path,
                )
            except Exception as e:
                logger.warning("Failed to load CA certificates: %s", str(e))

        # Set cipher suites
        try:
            context.set_ciphers(self.config.get_cipher_string())
        except ssl.SSLError as e:
            logger.warning("Failed to set custom ciphers: %s", str(e))

        # Disable compression
        context.options |= ssl.OP_NO_COMPRESSION

        logger.debug("Created client SSL context")

        return context

    def create_smtp_server_context(
        self,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
    ) -> ssl.SSLContext:
        """
        Create an SSL context specifically for SMTP server.

        Args:
            cert_file: Path to certificate file.
            key_file: Path to private key file.

        Returns:
            Configured SSLContext for SMTP server.
        """
        return self.create_server_context(cert_file, key_file, purpose="smtp")

    def create_smtp_client_context(
        self,
        verify: bool = True,
    ) -> ssl.SSLContext:
        """
        Create an SSL context specifically for SMTP client.

        Args:
            verify: Whether to verify server certificate.

        Returns:
            Configured SSLContext for SMTP client.
        """
        return self.create_client_context(verify=verify, check_hostname=verify)

    def create_http_server_context(
        self,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
    ) -> ssl.SSLContext:
        """
        Create an SSL context specifically for HTTP/HTTPS server.

        Args:
            cert_file: Path to certificate file.
            key_file: Path to private key file.

        Returns:
            Configured SSLContext for HTTP server.
        """
        return self.create_server_context(cert_file, key_file, purpose="http")


def create_default_tls_config(
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
) -> TLSConfig:
    """
    Create a TLS configuration with sensible defaults.

    Args:
        cert_file: Path to certificate file.
        key_file: Path to private key file.

    Returns:
        TLSConfig with modern security settings.
    """
    return TLSConfig(
        cert_file=cert_file,
        key_file=key_file,
        min_version=TLSVersion.TLS_1_2,
        max_version=TLSVersion.TLS_1_3,
        ciphers=TLS_1_2_CIPHERS,
        ciphersuites=TLS_1_3_CIPHERS,
        verify_mode=ssl.CERT_REQUIRED,
        check_hostname=True,
    )
