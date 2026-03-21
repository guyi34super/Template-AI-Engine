//! File parsers — XLSX, CSV, DOCX, PDF metadata extraction.
//!
//! Each parser accepts raw bytes via actix-web and returns structured JSON.

use actix_web::{web, HttpResponse};
use serde::Serialize;
use std::io::Cursor;

// ─── XLSX Parser (calamine) ───────────────────────────────────────
#[derive(Serialize)]
struct ParsedSheet {
    name: String,
    headers: Vec<String>,
    rows: Vec<Vec<serde_json::Value>>,
    row_count: usize,
}

#[derive(Serialize)]
struct XlsxResult {
    sheets: Vec<ParsedSheet>,
    total_sheets: usize,
}

pub async fn parse_xlsx(body: web::Bytes) -> HttpResponse {
    use calamine::{Reader, Xlsx, Data};

    let cursor = Cursor::new(body.to_vec());
    let mut workbook: Xlsx<_> = match Xlsx::new(cursor) {
        Ok(wb) => wb,
        Err(e) => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": format!("Failed to open XLSX: {}", e)}));
        }
    };

    let sheet_names: Vec<String> = workbook.sheet_names().to_vec();
    let mut sheets = Vec::new();

    for name in &sheet_names {
        if let Ok(range) = workbook.worksheet_range(name) {
            let mut rows_data: Vec<Vec<serde_json::Value>> = Vec::new();
            let mut headers: Vec<String> = Vec::new();
            let mut first = true;

            for row in range.rows() {
                let vals: Vec<serde_json::Value> = row
                    .iter()
                    .map(|cell| match cell {
                        Data::Empty => serde_json::Value::Null,
                        Data::String(s) => serde_json::Value::String(s.clone()),
                        Data::Float(f) => serde_json::json!(f),
                        Data::Int(i) => serde_json::json!(i),
                        Data::Bool(b) => serde_json::json!(b),
                        Data::DateTime(dt) => serde_json::json!(dt.to_string()),
                        _ => serde_json::Value::String(format!("{:?}", cell)),
                    })
                    .collect();

                if first {
                    headers = vals
                        .iter()
                        .enumerate()
                        .map(|(i, v)| match v {
                            serde_json::Value::String(s) => s.clone(),
                            _ => format!("column_{}", i),
                        })
                        .collect();
                    first = false;
                } else {
                    rows_data.push(vals);
                }
            }

            let row_count = rows_data.len();
            sheets.push(ParsedSheet {
                name: name.clone(),
                headers,
                rows: rows_data,
                row_count,
            });
        }
    }

    let total = sheets.len();
    HttpResponse::Ok().json(XlsxResult {
        sheets,
        total_sheets: total,
    })
}

// ─── CSV Parser ───────────────────────────────────────────────────
#[derive(Serialize)]
struct CsvResult {
    headers: Vec<String>,
    rows: Vec<Vec<String>>,
    row_count: usize,
}

pub async fn parse_csv(body: web::Bytes) -> HttpResponse {
    let cursor = Cursor::new(body.to_vec());
    let mut reader = csv::ReaderBuilder::new()
        .flexible(true)
        .from_reader(cursor);

    let headers: Vec<String> = match reader.headers() {
        Ok(h) => h.iter().map(|s| s.to_string()).collect(),
        Err(e) => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": format!("CSV header error: {}", e)}));
        }
    };

    let mut rows: Vec<Vec<String>> = Vec::new();
    for result in reader.records() {
        match result {
            Ok(record) => rows.push(record.iter().map(|s| s.to_string()).collect()),
            Err(e) => {
                log::warn!("CSV row parse error: {}", e);
            }
        }
    }

    let row_count = rows.len();
    HttpResponse::Ok().json(CsvResult {
        headers,
        rows,
        row_count,
    })
}

// ─── DOCX Parser (ZIP + quick-xml) ───────────────────────────────
#[derive(Serialize)]
struct DocxResult {
    paragraphs: Vec<String>,
    paragraph_count: usize,
    text: String,
}

pub async fn parse_docx(body: web::Bytes) -> HttpResponse {
    let cursor = Cursor::new(body.to_vec());
    let mut archive = match zip::ZipArchive::new(cursor) {
        Ok(a) => a,
        Err(e) => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": format!("Not a valid DOCX/ZIP: {}", e)}));
        }
    };

    // Read word/document.xml
    let xml_content = match archive.by_name("word/document.xml") {
        Ok(mut file) => {
            let mut buf = String::new();
            use std::io::Read;
            file.read_to_string(&mut buf).unwrap_or_default();
            buf
        }
        Err(_) => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "No word/document.xml found in DOCX"}));
        }
    };

    // Extract text from <w:t> elements using quick-xml
    let mut paragraphs: Vec<String> = Vec::new();
    let mut current_para = String::new();
    let mut in_text = false;

    let mut reader = quick_xml::Reader::from_str(&xml_content);
    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(quick_xml::events::Event::Start(ref e)) | Ok(quick_xml::events::Event::Empty(ref e)) => {
                let local_name = e.local_name();
                let local = reader.decoder().decode(local_name.as_ref()).unwrap_or_default();
                if local == "t" {
                    in_text = true;
                } else if local == "p" {
                    if !current_para.is_empty() {
                        paragraphs.push(current_para.clone());
                        current_para.clear();
                    }
                }
            }
            Ok(quick_xml::events::Event::Text(ref e)) => {
                if in_text {
                    if let Ok(text) = e.unescape() {
                        current_para.push_str(&text);
                    }
                }
            }
            Ok(quick_xml::events::Event::End(ref e)) => {
                let local_name = e.local_name();
                let local = reader.decoder().decode(local_name.as_ref()).unwrap_or_default();
                if local == "t" {
                    in_text = false;
                }
            }
            Ok(quick_xml::events::Event::Eof) => break,
            Err(e) => {
                log::warn!("XML parse error: {}", e);
                break;
            }
            _ => {}
        }
        buf.clear();
    }

    if !current_para.is_empty() {
        paragraphs.push(current_para);
    }

    let text = paragraphs.join("\n");
    let count = paragraphs.len();
    HttpResponse::Ok().json(DocxResult {
        paragraphs,
        paragraph_count: count,
        text,
    })
}

// ─── PDF Metadata (lopdf) ────────────────────────────────────────
#[derive(Serialize)]
struct PdfMetaResult {
    page_count: usize,
    metadata: serde_json::Value,
    text_preview: String,
}

pub async fn parse_pdf_meta(body: web::Bytes) -> HttpResponse {
    match lopdf::Document::load_mem(&body) {
        Ok(doc) => {
            let page_count = doc.get_pages().len();
            let mut meta = serde_json::Map::new();

            // Extract info dictionary
            if let Ok(info) = doc.trailer.get(b"Info") {
                if let Ok(info_ref) = info.as_reference() {
                    if let Ok(info_dict) = doc.get_dictionary(info_ref) {
                        for (key, val) in info_dict.iter() {
                            let key_str = String::from_utf8_lossy(key).to_string();
                            let val_str = format!("{:?}", val);
                            meta.insert(key_str, serde_json::Value::String(val_str));
                        }
                    }
                }
            }

            // Try to extract first page text preview (basic)
            let text_preview = doc
                .get_pages()
                .keys()
                .next()
                .and_then(|&page_num| doc.extract_text(&[page_num]).ok())
                .unwrap_or_default()
                .chars()
                .take(500)
                .collect::<String>();

            HttpResponse::Ok().json(PdfMetaResult {
                page_count,
                metadata: serde_json::Value::Object(meta),
                text_preview,
            })
        }
        Err(e) => HttpResponse::BadRequest()
            .json(serde_json::json!({"error": format!("PDF parse error: {}", e)})),
    }
}
