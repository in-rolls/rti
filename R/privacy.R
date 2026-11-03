public_assignment_columns <- c(
  "application_id", "authority_id", "batch_id", "state", "state_code", "office_name",
  "dept_group", "district", "block", "portal", "node_id", "tree_department", "tier", "treatment", "assigned_ra",
  "randomization_stratum", "template_version", "language", "channel"
)

public_assignments <- function(assignments) {
  assert_key(assignments, "application_id")
  public <- assignments[intersect(public_assignment_columns, names(assignments))]
  check_public_assignments(public)
  public
}

check_public_assignments <- function(rows) {
  if (any(!names(rows) %in% public_assignment_columns)) stop("Private or unrecognized columns in public assignments")
  assert_key(rows, "application_id")
  if (contains_contact_details(unlist(rows, use.names = FALSE))) stop("Contact details in public assignments")
  invisible(rows)
}

contains_contact_details <- function(text) {
  email <- "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
  phone <- "(^|[^0-9A-Za-z.])(?:[6-9][0-9]{9}|0[0-9]{10})([^0-9A-Za-z]|$)"
  any(grepl(paste(email, phone, sep = "|"), text, perl = TRUE))
}

find_private_files <- function(root = project_root) {
  args <- c("-C", shQuote(root), "ls-files", "--cached", "--others", "--exclude-standard")
  files <- system2("git", args, stdout = TRUE)
  files <- files[file.exists(file.path(root, files))]
  findings <- files[grepl("(^|/)(private|intake_raw)/|^config/filers?\\.yaml$|\\.(rds|sqlite|db|zip)$", files)]
  manifest <- read_manifest(root)
  frozen <- manifest$path[vapply(file.path(root, manifest$path), hash_file, character(1)) == manifest$sha256]
  inspect <- setdiff(files, frozen)
  inspect <- inspect[grepl("\\.(csv|txt|json|md|yaml|yml|html)$", inspect) & !grepl("^renv/", inspect)]
  private_columns <- c(
    "registration_number", "filed_by", "pio_name", "pio_email", "pio_phone", "payment_reference",
    "evidence_url", "screen_recording_url", "document_url"
  )
  for (file in inspect) {
    path <- file.path(root, file)
    if (grepl("\\.csv$", file)) {
      rows <- read_csv_text(path)
      columns <- intersect(names(rows), private_columns)
      if (any(vapply(rows[columns], function(values) any(nzchar(values)), logical(1)))) findings <- c(findings, file)
    }
    text <- paste(readLines(path, warn = FALSE), collapse = "\n")
    if (contains_contact_details(text)) findings <- c(findings, file)
    if (grepl("TGRTI/APP/|/R/20[0-9]{2}/[0-9]{4,}", text)) findings <- c(findings, file)
  }
  unique(findings)
}
