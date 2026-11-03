render_letter <- function(template, values) {
  placeholders <- unique(stringr::str_extract_all(template, "\\{[A-Za-z_][A-Za-z0-9_]*\\}")[[1]])
  fields <- gsub("[{}]", "", placeholders)
  if (any(!fields %in% names(values))) {
    stop("Missing letter fields: ", paste(setdiff(fields, names(values)), collapse = ", "))
  }
  for (i in seq_along(fields)) {
    value <- as.character(values[[fields[i]]])
    if (length(value) != 1L || is.na(value)) stop("Invalid letter field: ", fields[i])
    template <- stringr::str_replace_all(template, stringr::fixed(placeholders[i]), function(match) {
      rep(value, length(match))
    })
  }
  template
}

write_worklists <- function(assignments, directory) {
  assignments <- public_assignments(assignments)
  for (assistant in unique(assignments$assigned_ra)) {
    if (!grepl("^[A-Za-z0-9_-]+$", assistant)) stop("Invalid assistant identifier")
    write_csv_text(assignments[assignments$assigned_ra == assistant, ], file.path(directory, paste0(assistant, ".csv")))
  }
  invisible(directory)
}

render_batch_letters <- function(assignments, config, filer, directory, root = project_root) {
  assert_key(assignments, "application_id")
  template <- paste(readLines(file.path(root, config$instrument), warn = FALSE), collapse = "\n")
  legal <- paste(readLines(file.path(root, config$legal_salience), warn = FALSE), collapse = "\n")
  rendered <- lapply(seq_len(nrow(assignments)), function(i) {
    row <- assignments[i, ]
    values <- c(filer, list(
      authority = row$office_name, period_start = config$period_start,
      period_end = config$period_end, fee = config$fee,
      legal_salience = if (row$treatment == "legal_salience") legal else ""
    ))
    render_letter(template, values)
  })
  paths <- file.path(directory, assignments$assigned_ra, paste0(assignments$application_id, ".txt"))
  for (i in seq_along(paths)) {
    dir.create(dirname(paths[i]), recursive = TRUE, showWarnings = FALSE)
    writeLines(rendered[[i]], paths[i], useBytes = TRUE)
  }
  invisible(paths)
}
