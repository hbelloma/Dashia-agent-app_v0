# credentials_vault

Responde directo a la pregunta de "¿cómo se guardan las API de cada
usuario en su respectiva cuenta?" — el patrón de envelope encryption
del blueprint de seguridad (§2), implementado y probado (14 tests).

## Cómo funciona

```
Usuario pega su API key/secret en la app (pantalla "Conectar exchange")
        │
        ▼
crypto.py — se genera una DEK nueva, cifra el secreto con ella,
            y la DEK se cifra con la KEK maestra (envelope encryption real,
            librería `cryptography`, no un mock)
        │
        ▼
store.py — se guarda cifrado en la tabla `credentials`,
           llave (user_id, exchange, label) — cada usuario, cada
           exchange, aislado a nivel de SQL
        │
        ▼
connector_factory.py — cuando el agente necesita operar, se descifra
                        EN MEMORIA por un instante, se instancia el
                        conector correcto (Binance/Bybit/Weex), y el
                        texto plano nunca se loguea ni se vuelve a guardar
```

## La pieza más importante de probar — y se probó de verdad

`tests/test_store.py::test_raw_db_file_never_contains_plaintext_secrets`
no le pregunta al código "¿decís que cifrás?" — abre el archivo `.db`
como bytes crudos y confirma que el texto plano de la API key **no
está ahí**. Es la diferencia entre "el código dice que es seguro" y
"se verificó que lo es".

También se probó aislamiento real entre usuarios
(`test_multiple_users_are_isolated`): cada consulta filtra por
`user_id` a nivel de SQL, no trae todo y filtra después en Python —
así un bug de autorización en una capa superior no puede filtrar
accidentalmente las credenciales de otro usuario.

## Diferencia honesta con producción

Acá la KEK (master key) vive en una variable de entorno
(`VAULT_MASTER_KEY`) y el almacén es SQLite. Ambas cosas son
intencionalmente simples para que el paquete sea autocontenido y
testeable sin infraestructura externa. En producción:

- La KEK debe vivir en un **KMS/HSM gestionado** (AWS KMS, GCP KMS,
  HashiCorp Vault) — `crypto.py` está escrito para que ese cambio sea
  局部: solo `EnvelopeCipher.__init__` y `encrypt_secret`/`decrypt_secret`
  cambiarían de "cifrar localmente" a "pedirle al KMS que cifre/descifre
  la DEK", el resto del código no se entera del cambio.
- `store.py` se reemplaza por una tabla Postgres con las mismas
  columnas — la interfaz pública (`save_credential`, `get_credential`,
  `list_credentials`, `delete_credential`) no cambiaría.

## Las 3 diferencias reales entre exchanges que esto expone

| | Binance | Bybit | Weex |
|---|---|---|---|
| Verificación automática de "sin retiro" | ✅ `verify_trade_only()` | ✅ `verify_trade_only()` | ❌ no existe — requiere confirmación manual explícita (`acknowledge_manual_trade_only_check`) |
| `connect_and_verify()` marca la bóveda como verificada | Automático si pasa el chequeo | Automático si pasa el chequeo | Solo si `manual_trade_only_confirmed=True` |

Esto significa que la pantalla "Conectar exchange" del prototipo, para
Weex, tiene que mostrarle al usuario un paso extra: "revisa en tu
dashboard de Weex que la key no tenga retiro habilitado, y confírmalo
acá" — no es un detalle de implementación, es una diferencia real que
la UI necesita reflejar.

## Uso

```python
from credentials_vault.store import CredentialsVault
from credentials_vault.connector_factory import connect_and_verify

vault = CredentialsVault(db_path="vault.db")  # KEK desde VAULT_MASTER_KEY

# Cuando el usuario conecta su cuenta de Binance desde la app:
vault.save_credential(user_id="user_123", exchange="binance",
                       api_key="...", api_secret="...", testnet=True)
connector = connect_and_verify(vault, "user_123", "binance", market_type="spot")
# -> TradeOnlyViolation si la key tiene retiro habilitado; si no, queda
#    marcada como verificada y `connector` ya está listo para operar

# Para Weex, un paso más:
vault.save_credential(user_id="user_123", exchange="weex", api_key="...", api_secret="...")
connector = connect_and_verify(vault, "user_123", "weex",
                                manual_trade_only_confirmed=True)  # tras que el usuario lo confirme en la UI
```
