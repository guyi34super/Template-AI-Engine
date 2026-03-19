//! HMAC guard middleware — verifies X-Hmac-Signature header on incoming requests.
//!
//! Python signs each request body with HMAC-SHA256 using a shared secret.
//! This module verifies that signature before passing to handlers.

use crate::hashing;

/// Verify the HMAC signature from a request.
/// Returns true if the signature is valid.
pub fn verify_request_hmac(secret: &str, body: &[u8], signature: &str) -> bool {
    hashing::hmac_verify(secret.as_bytes(), body, signature)
}

/// Generate an HMAC signature for a response (for Python to verify).
pub fn sign_response(secret: &str, body: &[u8]) -> String {
    hashing::hmac_sha256(secret.as_bytes(), body)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verify_request() {
        let secret = "test-secret";
        let body = b"hello world";
        let sig = crate::hashing::hmac_sha256(secret.as_bytes(), body);
        assert!(verify_request_hmac(secret, body, &sig));
    }

    #[test]
    fn test_verify_bad_signature() {
        assert!(!verify_request_hmac("secret", b"data", "bad-sig"));
    }
}
