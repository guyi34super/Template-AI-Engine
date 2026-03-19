//! Type coercion — batch convert string values to target types.
//!
//! Used by the Python extraction pipeline to coerce OCR/raw text
//! into typed values (int, float, date, boolean, currency).

use serde::{Deserialize, Serialize};

#[derive(Deserialize, Clone)]
pub struct CoerceItem {
    pub field: String,
    pub value: String,
    pub target_type: String, // "integer", "float", "date", "boolean", "currency", "string"
}

#[derive(Serialize)]
pub struct CoerceResult {
    pub field: String,
    pub original: String,
    pub coerced: serde_json::Value,
    pub success: bool,
    pub error: Option<String>,
}

/// Coerce a single value to the target type.
pub fn coerce_value(item: &CoerceItem) -> CoerceResult {
    let trimmed = item.value.trim();

    let (coerced, success, error) = match item.target_type.as_str() {
        "integer" | "int" => {
            // Strip currency symbols, commas, spaces
            let cleaned: String = trimmed
                .chars()
                .filter(|c| c.is_ascii_digit() || *c == '-')
                .collect();
            match cleaned.parse::<i64>() {
                Ok(n) => (serde_json::json!(n), true, None),
                Err(e) => (serde_json::Value::Null, false, Some(format!("Cannot parse as integer: {}", e))),
            }
        }
        "float" | "number" | "decimal" => {
            let cleaned: String = trimmed
                .chars()
                .filter(|c| c.is_ascii_digit() || *c == '-' || *c == '.')
                .collect();
            match cleaned.parse::<f64>() {
                Ok(n) => (serde_json::json!(n), true, None),
                Err(e) => (serde_json::Value::Null, false, Some(format!("Cannot parse as float: {}", e))),
            }
        }
        "boolean" | "bool" => {
            let lower = trimmed.to_lowercase();
            match lower.as_str() {
                "true" | "yes" | "1" | "y" | "on" => (serde_json::json!(true), true, None),
                "false" | "no" | "0" | "n" | "off" => (serde_json::json!(false), true, None),
                _ => (serde_json::Value::Null, false, Some("Cannot parse as boolean".into())),
            }
        }
        "date" => {
            // Try common date formats
            let formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%Y/%m/%d",
                "%d-%m-%Y",
                "%d %B %Y",
                "%B %d, %Y",
            ];
            let mut parsed = None;
            for fmt in &formats {
                if chrono::NaiveDate::parse_from_str(trimmed, fmt).is_ok() {
                    parsed = Some(chrono::NaiveDate::parse_from_str(trimmed, fmt).unwrap());
                    break;
                }
            }
            match parsed {
                Some(d) => (serde_json::json!(d.format("%Y-%m-%d").to_string()), true, None),
                None => (serde_json::Value::Null, false, Some("Cannot parse date in any known format".into())),
            }
        }
        "currency" => {
            // Strip currency symbols e.g. R, $, €, £, ZAR, USD
            let cleaned: String = trimmed
                .replace(['R', '$', '€', '£', ',', ' '], "")
                .replace("ZAR", "")
                .replace("USD", "")
                .replace("EUR", "")
                .replace("GBP", "");
            match cleaned.trim().parse::<f64>() {
                Ok(n) => (serde_json::json!({"amount": n, "raw": trimmed}), true, None),
                Err(e) => (serde_json::Value::Null, false, Some(format!("Cannot parse currency: {}", e))),
            }
        }
        "string" | _ => {
            (serde_json::Value::String(trimmed.to_string()), true, None)
        }
    };

    CoerceResult {
        field: item.field.clone(),
        original: item.value.clone(),
        coerced,
        success,
        error,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_coerce_integer() {
        let item = CoerceItem {
            field: "age".into(),
            value: "  25  ".into(),
            target_type: "integer".into(),
        };
        let r = coerce_value(&item);
        assert!(r.success);
        assert_eq!(r.coerced, serde_json::json!(25));
    }

    #[test]
    fn test_coerce_float_with_comma() {
        let item = CoerceItem {
            field: "price".into(),
            value: "1,234.56".into(),
            target_type: "float".into(),
        };
        let r = coerce_value(&item);
        assert!(r.success);
    }

    #[test]
    fn test_coerce_boolean() {
        let item = CoerceItem {
            field: "active".into(),
            value: "Yes".into(),
            target_type: "boolean".into(),
        };
        let r = coerce_value(&item);
        assert!(r.success);
        assert_eq!(r.coerced, serde_json::json!(true));
    }

    #[test]
    fn test_coerce_date() {
        let item = CoerceItem {
            field: "dob".into(),
            value: "2024-01-15".into(),
            target_type: "date".into(),
        };
        let r = coerce_value(&item);
        assert!(r.success);
        assert_eq!(r.coerced, serde_json::json!("2024-01-15"));
    }

    #[test]
    fn test_coerce_currency() {
        let item = CoerceItem {
            field: "salary".into(),
            value: "R 15,000.00".into(),
            target_type: "currency".into(),
        };
        let r = coerce_value(&item);
        assert!(r.success);
    }
}
