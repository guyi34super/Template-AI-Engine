use actix_web::{web, App, HttpServer, HttpResponse, HttpRequest, middleware, dev::ServiceRequest};
use serde::{Deserialize, Serialize};
use std::env;
use std::sync::Arc;

mod validation;
mod hashing;
mod schema;
mod parser;
mod auth_verify;
mod coerce;
mod memory_index;
mod hmac_guard;

/// Shared application state injected via web::Data
pub struct AppState {
    pub hmac_secret: String,
}

// ─── Health ────────────────────────────────────────────────────────
async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "ok",
        "service": "rust-data-tier",
        "version": env!("CARGO_PKG_VERSION"),
        "port": env::var("RUST_PORT").unwrap_or_else(|_| "8001".into()),
    }))
}

// ─── Validate single ──────────────────────────────────────────────
#[derive(Deserialize)]
struct ValidateRequest {
    value: String,
    pattern: String,
}

#[derive(Serialize)]
struct ValidateResponse {
    valid: bool,
    value: String,
    pattern: String,
    error: Option<String>,
}

async fn validate(body: web::Json<ValidateRequest>) -> HttpResponse {
    match validation::validate_regex(&body.value, &body.pattern) {
        Ok(valid) => HttpResponse::Ok().json(ValidateResponse {
            valid,
            value: body.value.clone(),
            pattern: body.pattern.clone(),
            error: None,
        }),
        Err(e) => HttpResponse::BadRequest().json(ValidateResponse {
            valid: false,
            value: body.value.clone(),
            pattern: body.pattern.clone(),
            error: Some(e),
        }),
    }
}

// ─── Batch validate (Rayon parallel) ──────────────────────────────
#[derive(Deserialize, Clone)]
struct BatchItem {
    field: String,
    value: String,
    pattern: String,
}

#[derive(Serialize)]
struct BatchResult {
    field: String,
    valid: bool,
    error: Option<String>,
}

async fn validate_batch(body: web::Json<Vec<BatchItem>>) -> HttpResponse {
    use rayon::prelude::*;
    let items = body.into_inner();
    let results: Vec<BatchResult> = items
        .par_iter()
        .map(|item| {
            let (valid, error) = match validation::validate_regex(&item.value, &item.pattern) {
                Ok(v) => (v, None),
                Err(e) => (false, Some(e)),
            };
            BatchResult {
                field: item.field.clone(),
                valid,
                error,
            }
        })
        .collect();
    HttpResponse::Ok().json(results)
}

// ─── Test pattern (validate a regex itself) ───────────────────────
#[derive(Deserialize)]
struct TestPatternReq {
    pattern: String,
    sample_values: Vec<String>,
}

#[derive(Serialize)]
struct TestPatternRes {
    valid_pattern: bool,
    results: Vec<TestPatternMatch>,
    error: Option<String>,
}

#[derive(Serialize)]
struct TestPatternMatch {
    value: String,
    matches: bool,
}

async fn validate_test_pattern(body: web::Json<TestPatternReq>) -> HttpResponse {
    match regex::Regex::new(&body.pattern) {
        Ok(re) => {
            let results: Vec<TestPatternMatch> = body
                .sample_values
                .iter()
                .map(|v| TestPatternMatch {
                    value: v.clone(),
                    matches: re.is_match(v),
                })
                .collect();
            HttpResponse::Ok().json(TestPatternRes {
                valid_pattern: true,
                results,
                error: None,
            })
        }
        Err(e) => HttpResponse::BadRequest().json(TestPatternRes {
            valid_pattern: false,
            results: vec![],
            error: Some(format!("Invalid regex: {}", e)),
        }),
    }
}

// ─── Hash single ──────────────────────────────────────────────────
#[derive(Deserialize)]
struct HashRequest {
    data: String,
}

#[derive(Serialize)]
struct HashResponse {
    sha256: String,
}

async fn hash_data(body: web::Json<HashRequest>) -> HttpResponse {
    let hash = hashing::sha256_hex(&body.data);
    HttpResponse::Ok().json(HashResponse { sha256: hash })
}

// ─── Hash fields (map of field→value → field→hash) ───────────────
async fn hash_fields(body: web::Json<serde_json::Value>) -> HttpResponse {
    match body.as_object() {
        Some(map) => {
            let result: serde_json::Map<String, serde_json::Value> = map
                .iter()
                .map(|(k, v)| {
                    let val_str = match v {
                        serde_json::Value::String(s) => s.clone(),
                        other => other.to_string(),
                    };
                    (k.clone(), serde_json::Value::String(hashing::sha256_hex(&val_str)))
                })
                .collect();
            HttpResponse::Ok().json(serde_json::Value::Object(result))
        }
        None => HttpResponse::BadRequest().json(serde_json::json!({"error": "Expected JSON object"})),
    }
}

// ─── Hash file (binary upload) ────────────────────────────────────
async fn hash_file(body: web::Bytes) -> HttpResponse {
    let hash = hashing::sha256_bytes(&body);
    HttpResponse::Ok().json(serde_json::json!({ "sha256": hash, "size_bytes": body.len() }))
}

// ─── Hash verify-diff ─────────────────────────────────────────────
#[derive(Deserialize)]
struct VerifyDiffReq {
    original: serde_json::Value,
    current: serde_json::Value,
}

async fn hash_verify_diff(body: web::Json<VerifyDiffReq>) -> HttpResponse {
    let result = hashing::verify_diff(&body.original, &body.current);
    HttpResponse::Ok().json(result)
}

// ─── Schema coerce/flatten ────────────────────────────────────────
async fn schema_flatten(body: web::Json<serde_json::Value>) -> HttpResponse {
    let flat = schema::flatten_json(&body);
    HttpResponse::Ok().json(flat)
}

// ─── Coerce batch ─────────────────────────────────────────────────
async fn coerce_batch(body: web::Json<Vec<coerce::CoerceItem>>) -> HttpResponse {
    use rayon::prelude::*;
    let items = body.into_inner();
    let results: Vec<coerce::CoerceResult> = items
        .par_iter()
        .map(|item| coerce::coerce_value(item))
        .collect();
    HttpResponse::Ok().json(results)
}

// ─── Chunk text ───────────────────────────────────────────────────
#[derive(Deserialize)]
struct ChunkTextReq {
    text: String,
    chunk_size: Option<usize>,
    overlap: Option<usize>,
}

#[derive(Serialize)]
struct ChunkResult {
    chunks: Vec<ChunkItem>,
    total: usize,
}

#[derive(Serialize)]
struct ChunkItem {
    index: usize,
    text: String,
    char_start: usize,
    char_end: usize,
}

async fn chunk_text(body: web::Json<ChunkTextReq>) -> HttpResponse {
    let size = body.chunk_size.unwrap_or(512);
    let overlap = body.overlap.unwrap_or(64);
    let text = &body.text;
    let mut chunks = Vec::new();
    let mut start = 0usize;
    let mut idx = 0usize;

    while start < text.len() {
        let end = (start + size).min(text.len());
        // Try to break at whitespace
        let actual_end = if end < text.len() {
            text[start..end]
                .rfind(char::is_whitespace)
                .map(|p| start + p + 1)
                .unwrap_or(end)
        } else {
            end
        };
        chunks.push(ChunkItem {
            index: idx,
            text: text[start..actual_end].to_string(),
            char_start: start,
            char_end: actual_end,
        });
        idx += 1;
        start = if actual_end > overlap {
            actual_end - overlap
        } else {
            actual_end
        };
        if start >= actual_end && actual_end == text.len() {
            break;
        }
    }

    let total = chunks.len();
    HttpResponse::Ok().json(ChunkResult { chunks, total })
}

// ─── Rate limit check ─────────────────────────────────────────────
#[derive(Deserialize)]
struct RateLimitReq {
    key: String,
    limit: u64,
    window_secs: u64,
}

#[derive(Serialize)]
struct RateLimitRes {
    allowed: bool,
    current: u64,
    limit: u64,
    remaining: u64,
}

async fn ratelimit_check(body: web::Json<RateLimitReq>) -> HttpResponse {
    // In-memory sliding window using DashMap (no Redis dependency for this endpoint)
    use dashmap::DashMap;
    use once_cell::sync::Lazy;
    use std::time::{SystemTime, UNIX_EPOCH};

    static COUNTERS: Lazy<DashMap<String, Vec<u64>>> = Lazy::new(DashMap::new);

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let window_start = now.saturating_sub(body.window_secs);

    let mut entry = COUNTERS.entry(body.key.clone()).or_insert_with(Vec::new);
    // Prune old entries
    entry.retain(|&ts| ts > window_start);
    let current = entry.len() as u64;

    if current < body.limit {
        entry.push(now);
        let remaining = body.limit - current - 1;
        HttpResponse::Ok().json(RateLimitRes {
            allowed: true,
            current: current + 1,
            limit: body.limit,
            remaining,
        })
    } else {
        HttpResponse::Ok().json(RateLimitRes {
            allowed: false,
            current,
            limit: body.limit,
            remaining: 0,
        })
    }
}

// ─── Main ─────────────────────────────────────────────────────────
#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init();
    let host = env::var("RUST_HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
    let port: u16 = env::var("RUST_PORT")
        .unwrap_or_else(|_| "8001".to_string())
        .parse()
        .unwrap_or(8001);
    let hmac_secret = env::var("RUST_HMAC_SECRET").unwrap_or_else(|_| "dev-hmac-secret".to_string());

    let state = web::Data::new(AppState {
        hmac_secret: hmac_secret.clone(),
    });

    log::info!("Rust data-tier v{} starting on {}:{}", env!("CARGO_PKG_VERSION"), host, port);

    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .wrap(middleware::Logger::default())
            // Health (no HMAC required)
            .route("/health", web::get().to(health))
            // Validation
            .route("/validate", web::post().to(validate))
            .route("/validate/batch", web::post().to(validate_batch))
            .route("/validate/test-pattern", web::post().to(validate_test_pattern))
            // Hashing
            .route("/hash", web::post().to(hash_data))
            .route("/hash/fields", web::post().to(hash_fields))
            .route("/hash/file", web::post().to(hash_file))
            .route("/hash/verify-diff", web::post().to(hash_verify_diff))
            // Schema
            .route("/schema/flatten", web::post().to(schema_flatten))
            // Coerce
            .route("/coerce/batch", web::post().to(coerce_batch))
            // Chunking
            .route("/chunk/text", web::post().to(chunk_text))
            // Parsers
            .route("/parse/xlsx", web::post().to(parser::parse_xlsx))
            .route("/parse/csv", web::post().to(parser::parse_csv))
            .route("/parse/docx", web::post().to(parser::parse_docx))
            .route("/parse/pdf-meta", web::post().to(parser::parse_pdf_meta))
            // Auth verify
            .route("/auth/verify-jwt", web::post().to(auth_verify::verify_jwt))
            // Memory index
            .route("/memory/index", web::post().to(memory_index::build_keyword_index))
            // Rate limit
            .route("/ratelimit/check", web::post().to(ratelimit_check))
    })
    .bind((host.as_str(), port))?
    .workers(num_cpus::get().max(2))
    .run()
    .await
}
