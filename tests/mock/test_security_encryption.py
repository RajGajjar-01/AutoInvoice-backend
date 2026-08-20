import uuid
import pytest
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError

from app.core.security import (
    _get_all_master_keys,
    _get_master_encryption_key,
    decrypt_field,
    derive_tenant_key,
    encrypt_field,
    mask_account_number,
)
from app.schemas.company_settings import (
    CompanySettingsBase,
    CompanySettingsCreate,
    CompanySettingsUpdate,
)


class TestSecurityEncryption:
    def test_encrypt_decrypt_basic(self):
        owner_id = uuid.uuid4()
        plaintext = "123456789012"
        encrypted = encrypt_field(owner_id, plaintext)
        assert encrypted is not None
        assert encrypted.startswith("v1:")
        assert encrypted != plaintext

        decrypted = decrypt_field(owner_id, encrypted)
        assert decrypted == plaintext

    def test_encrypt_none_and_empty(self):
        owner_id = uuid.uuid4()
        assert encrypt_field(owner_id, None) is None
        assert encrypt_field(owner_id, "") == ""
        assert decrypt_field(owner_id, None) is None
        assert decrypt_field(owner_id, "") == ""

    def test_nonce_randomness(self):
        owner_id = uuid.uuid4()
        plaintext = "secret_bank_account_123"
        enc1 = encrypt_field(owner_id, plaintext)
        enc2 = encrypt_field(owner_id, plaintext)
        # Even with identical plaintext and owner_id, ciphertexts MUST differ due to random 96-bit nonce
        assert enc1 != enc2
        assert decrypt_field(owner_id, enc1) == plaintext
        assert decrypt_field(owner_id, enc2) == plaintext

    def test_tenant_isolation(self):
        owner_a = uuid.uuid4()
        owner_b = uuid.uuid4()
        plaintext = "secret_payout_account"

        enc_a = encrypt_field(owner_a, plaintext)

        # Tenant B must NOT be able to decrypt Tenant A's ciphertext
        with pytest.raises(ValueError, match="Failed to decrypt field"):
            decrypt_field(owner_b, enc_a)

    def test_tampering_detection(self):
        owner_id = uuid.uuid4()
        plaintext = "confidential_pan_number"
        encrypted = encrypt_field(owner_id, plaintext)
        assert encrypted is not None

        # Corrupt the ciphertext payload
        corrupted = encrypted[:-2] + ("A" if encrypted[-1] != "A" else "B") + "="
        with pytest.raises(ValueError, match="Failed to decrypt field"):
            decrypt_field(owner_id, corrupted)

    def test_mask_account_number(self):
        assert mask_account_number(None) is None
        assert mask_account_number("") == ""
        assert mask_account_number("123") == "***"
        assert mask_account_number("1234") == "****"
        assert mask_account_number("123456789012") == "********9012"


class TestFieldValidation:
    def test_valid_gstin(self):
        data = {
            "name": "Acme Corp",
            "gstin": "22AAAAA0000A1Z5",
        }
        obj = CompanySettingsBase(**data)
        assert obj.gstin == "22AAAAA0000A1Z5"

    def test_invalid_gstin_raises(self):
        data = {
            "name": "Acme Corp",
            "gstin": "INVALID_GST",
        }
        with pytest.raises(ValidationError):
            CompanySettingsBase(**data)

    def test_valid_pan(self):
        data = {
            "name": "Acme Corp",
            "pan": "ABCDE1234F",
        }
        obj = CompanySettingsBase(**data)
        assert obj.pan == "ABCDE1234F"

    def test_invalid_pan_raises(self):
        data = {
            "name": "Acme Corp",
            "pan": "12345ABCDE",
        }
        with pytest.raises(ValidationError):
            CompanySettingsBase(**data)

    def test_valid_ifsc(self):
        data = {
            "name": "Acme Corp",
            "bank_ifsc": "SBIN0001234",
        }
        obj = CompanySettingsBase(**data)
        assert obj.bank_ifsc == "SBIN0001234"

    def test_invalid_ifsc_raises(self):
        data = {
            "name": "Acme Corp",
            "bank_ifsc": "SBIN123",
        }
        with pytest.raises(ValidationError):
            CompanySettingsBase(**data)

    def test_valid_bank_account(self):
        data = {
            "name": "Acme Corp",
            "bank_account": "123456789012",
        }
        obj = CompanySettingsBase(**data)
        assert obj.bank_account == "123456789012"

    def test_invalid_bank_account_raises(self):
        data = {
            "name": "Acme Corp",
            "bank_account": "12345",  # Too short (< 9 digits)
        }
        with pytest.raises(ValidationError):
            CompanySettingsBase(**data)

    def test_valid_upi_id(self):
        data = {
            "name": "Acme Corp",
            "upi_id": "merchant@okhdfcbank",
        }
        obj = CompanySettingsBase(**data)
        assert obj.upi_id == "merchant@okhdfcbank"

    def test_invalid_upi_id_raises(self):
        data = {
            "name": "Acme Corp",
            "upi_id": "not-an-upi-id",
        }
        with pytest.raises(ValidationError):
            CompanySettingsBase(**data)
