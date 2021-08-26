# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""X509 certificates."""

from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import NamedTuple, Optional, Union

from OpenSSL import crypto

from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.snap import running_in_snap, SnapPaths


class Certificate(NamedTuple):
    """A self-signed X509 certificate with an associated key."""

    key: crypto.PKey
    cert: crypto.X509

    @classmethod
    def from_pem(cls, material: Union[bytes, str]):
        """Return a Certificate from PEM encoded material.

        The material is expected to contain both the certificate and private
        key.

        """
        key = crypto.load_privatekey(crypto.FILETYPE_PEM, material)
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, material)
        return cls(key, cert)

    def cn(self) -> str:
        """Return the certificate CN."""
        return self.cert.get_subject().CN

    def expiration(self) -> Optional[datetime]:
        """Return the certificate expiration."""
        expiry = self.cert.get_notAfter()
        if expiry is None:
            return None
        return datetime.strptime(expiry.decode("ascii"), "%Y%m%d%H%M%SZ")

    def public_key_pem(self) -> str:
        """Return PEM-encoded public key."""
        return crypto.dump_publickey(crypto.FILETYPE_PEM, self.key).decode(
            "ascii"
        )

    def private_key_pem(self) -> str:
        """Return PEM-encoded private key."""
        return crypto.dump_privatekey(crypto.FILETYPE_PEM, self.key).decode(
            "ascii"
        )

    def certificate_pem(self) -> str:
        """Return PEM-encoded certificate."""
        return crypto.dump_certificate(crypto.FILETYPE_PEM, self.cert).decode(
            "ascii"
        )

    def cert_hash(self) -> str:
        """Return the SHA-256 digest for the certificate."""
        return self.cert.digest("sha256").decode("ascii")


def generate_certificate(
    cn, key_bits=4096, validity=timedelta(days=3650)
) -> Certificate:
    """Generate an X509 certificate with an RSA private key."""
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, key_bits)

    cert = crypto.X509()
    cert.get_subject().CN = cn
    cert.set_serial_number(random.randint(0, (1 << 128) - 1))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(validity.total_seconds()))
    cert.set_pubkey(key)
    cert.sign(key, "sha512")
    return Certificate(key, cert)


def get_maas_cert_tuple():
    """Return a 2-tuple with certificate and private key paths.

    The format is the same used by python-requests."""
    if running_in_snap():
        cert_dir = SnapPaths.from_environ().common / "certificates"
        private_key = cert_dir / "maas.key"
        certificate = cert_dir / "maas.crt"
    else:
        private_key = Path(
            get_tentative_data_path("/etc/maas/certificates/maas.key")
        )
        certificate = Path(
            get_tentative_data_path("/etc/maas/certificates/maas.crt")
        )
    if not private_key.exists() or not certificate.exists():
        return None
    return str(certificate), str(private_key)
