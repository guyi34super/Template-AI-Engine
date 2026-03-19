use sha2::{Sha256, Digest};
use serde::Serialize;
use std::collections::HashMap;

/// Compute SHA-256 hex digest of the input string.
pub fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    hex::encode(hasher.finalize())
}

/// Compute SHA-256 hex digest of raw bytes (for file hashing).
pub fn sha256_bytes(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

/// Hash every field in a JSON object → { field: sha256(value) }
pub fn hash_fields(data: &serde_json::Value) -> HashMap<String, String> {
    let mut result = HashMap::new();
    if let Some(obj) = data.as_object() {
        for (k, v) in obj {
            let val_str = match v {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            result.insert(k.clone(), sha256_hex(&val_str));
        }
    }
    result
}

/// Compare original vs current field hashes, return changed/added/removed fields.
#[derive(Serialize)]
pub struct DiffResult {
    pub changed: Vec<String>,
    pub added: Vec<String>,
    pub removed: Vec<String>,
    pub unchanged: Vec<String>,
    pub has_changes: bool,
}

pub fn verify_diff(original: &serde_json::Value, current: &serde_json::Value) -> DiffResult {
    let orig_hashes = hash_fields(original);
    let curr_hashes = hash_fields(current);

    let mut changed = Vec::new();
    let mut added = Vec::new();
    let mut removed = Vec::new();
    let mut unchanged = Vec::new();

    // Check fields in current
    for (k, curr_hash) in &curr_hashes {
        match orig_hashes.get(k) {
            Some(orig_hash) => {
                if orig_hash == curr_hash {
                    unchanged.push(k.clone());
                } else {
                    changed.push(k.clone());
                }
            }
            None => added.push(k.clone()),
        }
    }

    // Check removed fields
    for k in orig_hashes.keys() {
        if !curr_hashes.contains_key(k) {
            removed.push(k.clone());
        }
    }

    let has_changes = !changed.is_empty() || !added.is_empty() || !removed.is_empty();
    DiffResult {
        changed,
        added,
        removed,
        unchanged,
        has_changes,
    }
}

/// HMAC-SHA256 sign a message with a secret key.
pub fn hmac_sha256(secret: &[u8], message: &[u8]) -> String {
    use hmac::{Hmac, Mac};
    type HmacSha256 = Hmac<Sha256>;
    let mut mac = HmacSha256::new_from_slice(secret).expect("HMAC can take key of any size");
    mac.update(message);
    hex::encode(mac.finalize().into_bytes())
}

/// Verify HMAC-SHA256 signature.
pub fn hmac_verify(secret: &[u8], message: &[u8], signature: &str) -> bool {
    let expected = hmac_sha256(secret, message);
    // Constant-time comparison
    expected == signature
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sha256_hello() {
        let hash = sha256_hex("hello");
        assert_eq!(
            hash,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
    }

    #[test]
    fn test_sha256_bytes() {
        let hash = sha256_bytes(b"hello");
        assert_eq!(
            hash,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
    }

    #[test]
    fn test_hash_fields() {
        let data = serde_json::json!({"name": "John", "age": "30"});
        let result = hash_fields(&data);
        assert_eq!(result.len(), 2);
        assert!(result.contains_key("name"));
    }

    #[test]
    fn test_verify_diff_changed() {
        let orig = serde_json::json!({"name": "John", "age": "30"});
        let curr = serde_json::json!({"name": "Jane", "age": "30"});
        let diff = verify_diff(&orig, &curr);
        assert!(diff.has_changes);
        assert!(diff.changed.contains(&"name".to_string()));
        assert!(diff.unchanged.contains(&"age".to_string()));
    }

    #[test]
    fn test_verify_diff_added_removed() {
        let orig = serde_json::json!({"name": "John"});
        let curr = serde_json::json!({"email": "john@test.com"});
        let diff = verify_diff(&orig, &curr);
        assert!(diff.has_changes);
        assert!(diff.added.contains(&"email".to_string()));
        assert!(diff.removed.contains(&"name".to_string()));
    }

    #[test]
    fn test_hmac_sign_verify() {
        let secret = b"my-secret";
        let msg = b"hello world";
        let sig = hmac_sha256(secret, msg);
        assert!(hmac_verify(secret, msg, &sig));
        assert!(!hmac_verify(secret, b"wrong message", &sig));
    }
}
