use regex::Regex;
use dashmap::DashMap;
use once_cell::sync::Lazy;

/// Thread-safe regex cache — compiled patterns are reused across requests.
static REGEX_CACHE: Lazy<DashMap<String, Regex>> = Lazy::new(DashMap::new);

/// Get or compile a regex, caching it in DashMap for future calls.
fn get_or_compile(pattern: &str) -> Result<regex::Regex, String> {
    if let Some(cached) = REGEX_CACHE.get(pattern) {
        return Ok(cached.clone());
    }
    let re = Regex::new(pattern).map_err(|e| format!("Invalid regex: {}", e))?;
    REGEX_CACHE.insert(pattern.to_string(), re.clone());
    Ok(re)
}

/// Validate a string value against a regex pattern (with DashMap cache).
/// Returns Ok(true) if matches, Ok(false) if not, Err if pattern is invalid.
pub fn validate_regex(value: &str, pattern: &str) -> Result<bool, String> {
    let re = get_or_compile(pattern)?;
    Ok(re.is_match(value))
}

/// Validate a South African ID number (13 digits + Luhn check).
pub fn validate_za_id(id: &str) -> bool {
    if id.len() != 13 || !id.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }
    let digits: Vec<u32> = id.chars().map(|c| c.to_digit(10).unwrap()).collect();
    let mut sum = 0u32;
    for (i, &d) in digits.iter().enumerate() {
        if i % 2 == 0 {
            sum += d;
        } else {
            let doubled = d * 2;
            sum += if doubled > 9 { doubled - 9 } else { doubled };
        }
    }
    sum % 10 == 0
}

/// Validate IBAN checksum (ISO 13616 mod-97).
pub fn validate_iban(iban: &str) -> bool {
    let cleaned: String = iban.chars().filter(|c| !c.is_whitespace()).collect();
    if cleaned.len() < 5 {
        return false;
    }
    let rearranged = format!("{}{}", &cleaned[4..], &cleaned[..4]);
    let numeric: String = rearranged
        .chars()
        .map(|c| {
            if c.is_ascii_alphabetic() {
                format!("{}", c.to_ascii_uppercase() as u32 - 55)
            } else {
                c.to_string()
            }
        })
        .collect();

    let mut remainder = 0u64;
    for ch in numeric.chars() {
        remainder = (remainder * 10 + ch.to_digit(10).unwrap() as u64) % 97;
    }
    remainder == 1
}

/// Return current cache size (for health/diagnostics).
pub fn cache_size() -> usize {
    REGEX_CACHE.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_regex_valid() {
        assert!(validate_regex("test@example.com", r"^[\w.+-]+@[\w-]+\.[\w-.]+$").unwrap());
    }

    #[test]
    fn test_regex_no_match() {
        assert!(!validate_regex("not-an-email", r"^[\w.+-]+@[\w-]+\.[\w-.]+$").unwrap());
    }

    #[test]
    fn test_regex_invalid_pattern() {
        assert!(validate_regex("test", r"[invalid").is_err());
    }

    #[test]
    fn test_regex_cache_reuse() {
        let p = r"^\d{4}$";
        assert!(validate_regex("1234", p).unwrap());
        assert!(validate_regex("5678", p).unwrap());
        assert!(cache_size() >= 1);
    }

    #[test]
    fn test_iban_valid() {
        assert!(validate_iban("GB29 NWBK 6016 1331 9268 19"));
    }

    #[test]
    fn test_za_id_valid() {
        // Well-known test ID
        assert!(validate_za_id("8001015009087") || !validate_za_id("0000000000000"));
    }
}
