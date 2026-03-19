use serde_json::{Map, Value};

/// Flatten a nested JSON object into a single-level map with dot-delimited keys.
///
/// Example:
///   {"a": {"b": 1, "c": [2,3]}}  →  {"a.b": 1, "a.c.0": 2, "a.c.1": 3}
pub fn flatten_json(value: &Value) -> Value {
    let mut out = Map::new();
    _flatten(value, String::new(), &mut out);
    Value::Object(out)
}

fn _flatten(value: &Value, prefix: String, out: &mut Map<String, Value>) {
    match value {
        Value::Object(map) => {
            for (k, v) in map {
                let key = if prefix.is_empty() {
                    k.clone()
                } else {
                    format!("{}.{}", prefix, k)
                };
                _flatten(v, key, out);
            }
        }
        Value::Array(arr) => {
            for (i, v) in arr.iter().enumerate() {
                let key = format!("{}.{}", prefix, i);
                _flatten(v, key, out);
            }
        }
        _ => {
            out.insert(prefix, value.clone());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_flatten_nested() {
        let input = json!({"a": {"b": 1, "c": [2, 3]}});
        let flat = flatten_json(&input);
        assert_eq!(flat["a.b"], 1);
        assert_eq!(flat["a.c.0"], 2);
        assert_eq!(flat["a.c.1"], 3);
    }

    #[test]
    fn test_flatten_simple() {
        let input = json!({"x": "hello"});
        let flat = flatten_json(&input);
        assert_eq!(flat["x"], "hello");
    }
}
