read_csv_text <- function(path) {
  readr::read_csv(path,
    col_types = readr::cols(.default = "c"), na = character(),
    show_col_types = FALSE, name_repair = "minimal"
  )
}

write_csv_text <- function(rows, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(rows, path, na = "")
  invisible(path)
}

hash_file <- function(path) digest::digest(file = path, algo = "sha256")

save_rds_atomic <- function(value, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  staged <- tempfile(tmpdir = dirname(path))
  on.exit(unlink(staged))
  saveRDS(value, staged)
  if (!file.rename(staged, path)) stop("Could not save state: ", path)
  invisible(path)
}
hash_text <- function(text, length = 16L, algorithm = "sha256") {
  vapply(enc2utf8(text), function(value) {
    substr(digest::digest(value, algo = algorithm, serialize = FALSE), 1, length)
  }, character(1), USE.NAMES = FALSE)
}

normalize_text <- function(text) stringr::str_squish(dplyr::coalesce(text, ""))
normalize_key <- function(text) stringr::str_to_lower(normalize_text(text), locale = "en")

make_authority_id <- function(state, office, district = "", block = "", occurrence = 1L) {
  keys <- paste(normalize_key(state), normalize_key(office), normalize_key(district),
    normalize_key(block),
    sep = "|"
  )
  occurrence <- rep_len(occurrence, length(keys))
  keys <- ifelse(occurrence > 1L, paste0(keys, "|occurrence:", occurrence), keys)
  hash_text(keys, 12L)
}

make_application_id <- function(state_code, sequence) sprintf("%s-%03d", state_code, sequence)
next_sequence <- function(issued, state_code) {
  matches <- issued[grepl(paste0("^", state_code, "-[0-9]+$"), issued)]
  if (!length(matches)) {
    return(1L)
  }
  max(as.integer(sub("^[A-Z]+-", "", matches))) + 1L
}

assert_key <- function(rows, key) {
  if (!key %in% names(rows) || anyNA(rows[[key]]) || any(!nzchar(rows[[key]])) || anyDuplicated(rows[[key]])) {
    stop("Missing or duplicate key: ", key)
  }
  invisible(rows)
}

read_manifest <- function(root = project_root) read_csv_text(file.path(root, "docs", "source_manifest.csv"))
verify_sources <- function(root = project_root) {
  manifest <- read_manifest(root)
  paths <- file.path(root, manifest$path)
  if (any(!file.exists(paths))) stop("Missing source: ", manifest$path[!file.exists(paths)][1])
  actual <- vapply(paths, hash_file, character(1))
  if (any(actual != manifest$sha256)) stop("Changed frozen source: ", manifest$path[actual != manifest$sha256][1])
  invisible(manifest)
}
