"""Store the public chain of every PKCS#12 Sign Certificate, so verification no longer opens the seal (P3.8)."""

from frappe_sign.services import certificates


def execute() -> None:
	certificates.backfill_public_chain()
