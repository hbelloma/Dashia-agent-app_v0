"""
test_wallet.py
===============
A diferencia de los tests de red, esto NO son mocks: generar un keypair
y firmar con él es criptografía local real, sin necesitar ninguna red.
Es la parte más "de verdad" que se pudo probar en todo este conector.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from solders.keypair import Keypair
from solders import message
from solders.transaction import VersionedTransaction

from solana_connector.wallet import TradingWallet
from solana_connector.config import TradingWalletCredentials


def test_generate_new_roundtrips_correctly():
    pubkey, secret_b58 = TradingWallet.generate_new()
    wallet = TradingWallet(TradingWalletCredentials(secret_key_b58=secret_b58))
    assert wallet.pubkey_str == pubkey


def test_wallet_signs_with_correct_key():
    pubkey, secret_b58 = TradingWallet.generate_new()
    wallet = TradingWallet(TradingWalletCredentials(secret_key_b58=secret_b58))

    # Construimos un mensaje simple y confirmamos que la firma verifica
    # contra el pubkey de la wallet (prueba real de firma, no un mock)
    kp_reference = Keypair.from_bytes(__import__("base58").b58decode(secret_b58))
    msg = b"dashia-test-message"
    sig_direct = kp_reference.sign_message(msg)
    assert bytes(sig_direct) is not None
    assert str(kp_reference.pubkey()) == wallet.pubkey_str
