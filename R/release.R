read_assignments <- function(frame, root = project_root) {
  catalog <- read_csv_text(file.path(root, "config", "batches.csv"))
  rows <- lapply(seq_len(nrow(catalog)), function(i) {
    batch <- catalog[i, ]
    assignments <- read_csv_text(file.path(root, batch$path))
    if (any(assignments$batch_id != batch$batch_id) || nrow(assignments) != as.integer(batch$n)) {
      stop("Batch catalog mismatch")
    }
    assignments$state_code <- sub("-.*", "", assignments$application_id)
    if (!"dept_group" %in% names(assignments)) assignments$dept_group <- assignments$tree_department
    if (!"randomization_stratum" %in% names(assignments)) assignments$randomization_stratum <- "batch"
    if (!"authority_id" %in% names(assignments)) {
      # Exact portal names disambiguate offices whose normalized spellings coincide.
      key <- function(state, office) paste(state, office, sep = "|")
      index <- match(key(assignments$state, assignments$office_name), key(frame$state, frame$office_name))
      if (anyNA(index)) stop("Assignment has no exact frame match: ", assignments$application_id[is.na(index)][1])
      assignments$authority_id <- frame$authority_id[index]
    }
    assignments
  })
  assignments <- dplyr::bind_rows(rows)
  for (column in names(assignments)) assignments[[column]][is.na(assignments[[column]])] <- ""
  assert_key(assignments, "application_id")
  if (any(!assignments$authority_id %in% frame$authority_id)) stop("Assignment references an unknown authority")
  if (anyDuplicated(assignments$authority_id)) stop("Office selected in multiple frozen batches")
  assignments
}

build_release <- function(root = project_root) {
  verify_sources(root)
  frame <- build_frames(root)
  assignments <- public_assignments(read_assignments(frame, root))
  check_public_assignments(assignments)
  directory <- file.path(root, "data", "release")
  write_csv_text(frame, file.path(directory, "authorities.csv"))
  write_csv_text(assignments, file.path(directory, "assignments.csv"))
  paths <- c("authorities.csv", "assignments.csv")
  manifest <- data.frame(path = paths, sha256 = vapply(file.path(directory, paths), hash_file, character(1)))
  write_csv_text(manifest, file.path(directory, "checksums.csv"))
  invisible(list(authorities = frame, assignments = assignments))
}

build_site <- function(release, root = project_root, directory = file.path(root, "_site")) {
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  file.copy(list.files(file.path(root, "site"), full.names = TRUE), directory, overwrite = TRUE)
  data <- file.path(directory, "data")
  dir.create(data, recursive = TRUE, showWarnings = FALSE)
  assignments <- public_assignments(release$assignments)
  jsonlite::write_json(assignments, file.path(data, "assignments.json"), dataframe = "rows", auto_unbox = TRUE)
  write_csv_text(assignments, file.path(data, "assignments.csv"))
  write_worklists(assignments, file.path(data, "worklists"))
  # Serve the hashed, issued instruments directly; no second rendering pipeline.
  file.copy(file.path(root, "data", "reference", "batches"), directory, recursive = TRUE, overwrite = TRUE)
  instruments <- read_csv_text(file.path(root, "config", "instruments.csv"))
  if (any(!file.exists(file.path(directory, "batches", instruments$path)))) stop("Missing issued instrument")
  instruments$name <- paste(instruments$treatment, instruments$template_version)
  instruments$path <- paste0("batches/", instruments$path)
  jsonlite::write_json(instruments, file.path(data, "instruments.json"), dataframe = "rows", auto_unbox = TRUE)
  invisible(directory)
}

read_issued_assignments <- function(root = project_root) {
  frozen <- read_assignments(build_frames(root), root)
  path <- file.path(root, "data", "private", "batches.rds")
  if (!file.exists(path)) {
    return(frozen)
  }
  batches <- readRDS(path)
  issued <- dplyr::bind_rows(c(list(frozen), lapply(batches, `[[`, "assignments")))
  assert_key(issued, "application_id")
  assert_key(issued, "authority_id")
  issued
}

register_batch <- function(batch, issued) {
  rows <- batch$assignments
  for (key in c("application_id", "authority_id")) {
    assert_key(rows, key)
    if (any(rows[[key]] %in% issued[[key]])) stop("Batch conflicts with issued ", key)
  }
  if (length(unique(rows$batch_id)) != 1L || any(rows$batch_id %in% issued$batch_id)) {
    stop("Batch ID already issued or invalid")
  }
  if (!all(c("template_version", "language", "channel", "assigned_ra", "treatment") %in% names(rows))) {
    stop("Batch lacks required instrument or assignment fields")
  }
  if (any(!rows$treatment %in% c("plain", "legal_salience"))) stop("Invalid treatment")
  invisible(batch)
}
