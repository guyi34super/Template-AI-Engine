//! JWT verification endpoint — delegates RS256/HS256 verify from Python.
//!
//! Python sends the raw JWT string; Rust decodes and verifies claims.

use actix_web::{web, HttpResponse};
use serde::{Deserialize, Serialize};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use std::env;

#[derive(Deserialize)]
pub struct VerifyJwtReq {
    token: String,
    /// "RS256" or "HS256"
    algorithm: Option<String>,
}

#[derive(Serialize)]
pub struct VerifyJwtRes {
    valid: bool,
    claims: Option<serde_json::Value>,
    error: Option<String>,
}

/// Standard JWT claims we expect
#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    sub: Option<String>,
    email: Option<String>,
    role: Option<String>,
    jti: Option<String>,
    #[serde(rename = "type")]
    token_type: Option<String>,
    iat: Option<u64>,
    exp: Option<u64>,
}

pub async fn verify_jwt(body: web::Json<VerifyJwtReq>) -> HttpResponse {
    let alg_str = body.algorithm.as_deref().unwrap_or("HS256");
    let (algorithm, key) = match alg_str {
        "RS256" => {
            let pem = env::var("JWT_PUBLIC_KEY").unwrap_or_default();
            if pem.is_empty() {
                return HttpResponse::Ok().json(VerifyJwtRes {
                    valid: false,
                    claims: None,
                    error: Some("JWT_PUBLIC_KEY not configured".into()),
                });
            }
            match DecodingKey::from_rsa_pem(pem.as_bytes()) {
                Ok(dk) => (Algorithm::RS256, dk),
                Err(e) => {
                    return HttpResponse::Ok().json(VerifyJwtRes {
                        valid: false,
                        claims: None,
                        error: Some(format!("Invalid RSA key: {}", e)),
                    });
                }
            }
        }
        _ => {
            let secret = env::var("JWT_SECRET").unwrap_or_else(|_| "dev-secret-key-change-in-production".into());
            (Algorithm::HS256, DecodingKey::from_secret(secret.as_bytes()))
        }
    };

    let mut validation = Validation::new(algorithm);
    validation.validate_exp = true;

    match decode::<Claims>(&body.token, &key, &validation) {
        Ok(token_data) => {
            let claims_json = serde_json::to_value(&token_data.claims).unwrap_or_default();
            HttpResponse::Ok().json(VerifyJwtRes {
                valid: true,
                claims: Some(claims_json),
                error: None,
            })
        }
        Err(e) => HttpResponse::Ok().json(VerifyJwtRes {
            valid: false,
            claims: None,
            error: Some(format!("{}", e)),
        }),
    }
}
