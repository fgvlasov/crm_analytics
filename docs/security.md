# Security

- Secrets encrypted at rest (Fernet derived from `ENCRYPTION_MASTER_KEY`)
- Passwords hashed with bcrypt
- JWT access/refresh tokens
- Log redaction for password/token/key patterns
- No plaintext secrets in API responses (`SecretOut` excludes ciphertext)

See `.cursorrules/12_SECURITY_COMPLIANCE.md`.
