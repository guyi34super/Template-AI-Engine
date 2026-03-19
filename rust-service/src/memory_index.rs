//! Memory keyword index — build inverted keyword index for memory entries.
//!
//! Takes text + metadata, extracts keywords, returns TF-IDF-like scores.

use actix_web::{web, HttpResponse};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use rayon::prelude::*;

#[derive(Deserialize)]
pub struct IndexRequest {
    pub entries: Vec<MemoryEntryInput>,
}

#[derive(Deserialize, Clone)]
pub struct MemoryEntryInput {
    pub id: String,
    pub text: String,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Serialize)]
pub struct IndexResult {
    pub entries: Vec<IndexedEntry>,
    pub total_keywords: usize,
    pub processing_time_ms: u64,
}

#[derive(Serialize)]
pub struct IndexedEntry {
    pub id: String,
    pub keywords: Vec<KeywordScore>,
    pub word_count: usize,
}

#[derive(Serialize, Clone)]
pub struct KeywordScore {
    pub keyword: String,
    pub tf: f64,
    pub df: usize,
}

/// Stop words to filter out (common English).
const STOP_WORDS: &[&str] = &[
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "but", "and", "or", "if", "that", "this", "these", "those", "it",
    "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
];

fn is_stop_word(w: &str) -> bool {
    STOP_WORDS.contains(&w)
}

fn extract_keywords(text: &str) -> HashMap<String, usize> {
    let mut freq: HashMap<String, usize> = HashMap::new();
    for word in text.split_whitespace() {
        let cleaned: String = word
            .chars()
            .filter(|c| c.is_alphanumeric() || *c == '-' || *c == '_')
            .collect::<String>()
            .to_lowercase();

        if cleaned.len() < 2 || is_stop_word(&cleaned) {
            continue;
        }
        *freq.entry(cleaned).or_insert(0) += 1;
    }
    freq
}

pub async fn build_keyword_index(body: web::Json<IndexRequest>) -> HttpResponse {
    let start = std::time::Instant::now();
    let entries = &body.entries;

    // Phase 1: Extract keywords per entry (parallel)
    let per_entry_keywords: Vec<(String, HashMap<String, usize>, usize)> = entries
        .par_iter()
        .map(|entry| {
            let kw = extract_keywords(&entry.text);
            let word_count: usize = kw.values().sum();
            (entry.id.clone(), kw, word_count)
        })
        .collect();

    // Phase 2: Compute document frequency
    let mut doc_freq: HashMap<String, usize> = HashMap::new();
    for (_, kw_map, _) in &per_entry_keywords {
        for key in kw_map.keys() {
            *doc_freq.entry(key.clone()).or_insert(0) += 1;
        }
    }

    // Phase 3: Build indexed entries with TF scores
    let total_docs = entries.len().max(1);
    let mut all_keywords: HashMap<String, bool> = HashMap::new();

    let indexed: Vec<IndexedEntry> = per_entry_keywords
        .iter()
        .map(|(id, kw_map, word_count)| {
            let wc = (*word_count).max(1) as f64;
            let mut keywords: Vec<KeywordScore> = kw_map
                .iter()
                .map(|(k, &count)| {
                    all_keywords.insert(k.clone(), true);
                    let tf = count as f64 / wc;
                    let df = *doc_freq.get(k).unwrap_or(&1);
                    KeywordScore {
                        keyword: k.clone(),
                        tf,
                        df,
                    }
                })
                .collect();
            // Sort by TF descending, keep top 50
            keywords.sort_by(|a, b| b.tf.partial_cmp(&a.tf).unwrap_or(std::cmp::Ordering::Equal));
            keywords.truncate(50);

            IndexedEntry {
                id: id.clone(),
                keywords,
                word_count: *word_count,
            }
        })
        .collect();

    let elapsed = start.elapsed().as_millis() as u64;
    HttpResponse::Ok().json(IndexResult {
        entries: indexed,
        total_keywords: all_keywords.len(),
        processing_time_ms: elapsed,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_keywords() {
        let kw = extract_keywords("The quick brown fox jumps over the lazy dog");
        assert!(kw.contains_key("quick"));
        assert!(kw.contains_key("fox"));
        assert!(!kw.contains_key("the")); // stop word
    }

    #[test]
    fn test_extract_keywords_dedup() {
        let kw = extract_keywords("hello hello hello world");
        assert_eq!(*kw.get("hello").unwrap(), 3);
        assert_eq!(*kw.get("world").unwrap(), 1);
    }
}
