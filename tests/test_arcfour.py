import pytest
from pdf2zh.arcfour import Arcfour


def arcfour_encrypt(plaintext: bytes, key: bytes) -> bytes:
    cipher = Arcfour(key)
    return cipher.encrypt(plaintext)


def arcfour_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    cipher = Arcfour(key)
    return cipher.decrypt(ciphertext)


def test_basic_functionality():
    plaintext = b"Hello, World!"
    key = b"mysecretkey"
    ciphertext = arcfour_encrypt(plaintext, key)
    decrypted_text = arcfour_decrypt(ciphertext, key)
    assert decrypted_text == plaintext

def test_ciphertext():
    plaintext = b"Hello, World!"
    key = b"mysecretkey"
    ciphertext = arcfour_encrypt(plaintext, key)
    assert ciphertext.hex() == "a2b614d4af651ec7af7f5259db"

def test_empty_plaintext():
    plaintext = b""
    key = b"testkey"
    ciphertext = arcfour_encrypt(plaintext, key)
    decrypted_text = arcfour_decrypt(ciphertext, key)
    assert decrypted_text == plaintext


def test_empty_key():
    plaintext = b"Test data"
    key = b""
    with pytest.raises(ValueError):  # Key must be non-empty
        arcfour_encrypt(plaintext, key)


def test_large_key():
    plaintext = b"Test data"
    key = b"X" * 256
    with pytest.raises(ValueError):  # Key must be less than 256 bytes
        arcfour_encrypt(plaintext, key)

def test_large_key2():
    plaintext = b"Test data"
    key = b"X" * 255
    ciphertext = arcfour_encrypt(plaintext, key)
    decrypted_text = arcfour_decrypt(ciphertext, key)
    assert decrypted_text == plaintext

def test_randomness():
    plaintext = b"AAAAA"
    key = b"randomkey"
    ciphertexts = [arcfour_encrypt(plaintext, key) for _ in range(10)]
    assert len(set(ciphertexts)) <= 1  # All ciphertexts should be the same
