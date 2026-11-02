form_key <- function(value) trimws(gsub("[^a-z0-9]+", " ", tolower(value)))

read_form <- function(rows, form, root = project_root) {
  mapping <- yaml::read_yaml(file.path(root, "config", "forms.yaml"))[[form]]
  if (is.null(mapping)) stop("Unknown form: ", form)
  columns <- form_key(names(rows))
  if (anyDuplicated(columns)) stop("Ambiguous form headings")
  result <- lapply(mapping, function(aliases) {
    matches <- match(form_key(unlist(aliases)), columns)
    matches <- matches[!is.na(matches)]
    if (length(matches)) trimws(rows[[matches[1]]]) else rep("", nrow(rows))
  })
  result <- as.data.frame(result, stringsAsFactors = FALSE)
  result$application_id <- toupper(result$application_id)
  result
}

coerce_choice <- function(value, field, vocab = vocabularies) {
  lookup <- c(
    payment_mode = "payment_modes", medium = "mediums", event_type = "event_types",
    not_filed_reason = "not_filed_reasons", filing_outcome = "filing_outcomes"
  )
  allowed <- vocab[[lookup[[field]]]]
  labels <- vocab[[paste0(field, "_labels")]]
  mapping <- setNames(allowed, form_key(allowed))
  if (!is.null(labels)) mapping <- c(mapping, setNames(names(labels), form_key(unlist(labels))))
  if (field == "filing_outcome") mapping <- c(mapping, yes = "filed", no = "not_filed", "not filed" = "not_filed")
  result <- unname(mapping[form_key(value)])
  result[!nzchar(value)] <- ""
  if (anyNA(result)) stop("Unrecognized ", field, ": ", value[is.na(result)][1])
  result
}

blank_table <- function(columns) as.data.frame(setNames(rep(list(character()), length(columns)), columns))

new_intake <- function(assignments) {
  assert_key(assignments, "application_id")
  applications <- assignments
  fields <- c(
    "filing_outcome", "not_filed_reason", "filing_date", "registration_number", "fee_paid_inr",
    "payment_mode", "payment_reference", "evidence_url", "screen_recording_url", "filed_by", "due_date", "notes"
  )
  for (field in setdiff(fields, names(applications))) applications[[field]] <- ""
  list(
    applications = applications,
    events = blank_table(c(
      "event_id", "application_id", "event_type", "event_date", "medium", "direction",
      "actor_authority", "document_url", "recorded_by", "recorded_at", "notes", "source_row_id"
    )),
    submissions = blank_table(c("source_row_id", "form", "application_id", "timestamp", "payload_sha256"))
  )
}

validate_date <- function(value, required = FALSE) {
  valid <- grepl("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", value) & !is.na(as.Date(value, format = "%Y-%m-%d"))
  if (any((nzchar(value) | required) & !valid)) stop("Expected an ISO date (YYYY-MM-DD)")
  invisible(value)
}

apply_form <- function(state, rows, form, rules, vocab = vocabularies) {
  assert_key(state$applications, "application_id")
  required <- c("application_id", "timestamp")
  if (!all(required %in% names(rows))) stop("Missing form identifiers")
  if (any(!nzchar(rows$application_id) | !nzchar(rows$timestamp))) stop("Blank form identifiers")
  if (any(!rows$application_id %in% state$applications$application_id)) stop("Unknown application in form")
  if (!form %in% c("filing", "update")) stop("Unknown form")
  rows$source_row_id <- hash_text(paste(form, rows$timestamp, rows$application_id, sep = "|"))
  for (i in seq_len(nrow(rows))) {
    row <- rows[i, , drop = FALSE]
    fields <- sort(setdiff(names(row), "source_row_id"))
    payload <- digest::digest(as.list(row[fields]), algo = "sha256")
    seen <- match(row$source_row_id, state$submissions$source_row_id)
    if (!is.na(seen)) {
      if (state$submissions$payload_sha256[seen] != payload) stop("Previously processed submission changed")
      next
    }
    target <- match(row$application_id, state$applications$application_id)
    if (form == "filing") {
      for (field in c("filing_outcome", "not_filed_reason", "payment_mode")) {
        row[[field]] <- coerce_choice(row[[field]], field, vocab)
      }
      if (!nzchar(row$filing_outcome)) stop("Missing filing outcome")
      if (row$filing_outcome == "filed") {
        validate_date(row$filing_date, required = TRUE)
        rule <- rules[[state$applications$state[target]]]
        if (is.null(rule)) rule <- rules$`_default`
        if (is.null(rule$statutory_days)) stop("Missing response period for state")
        row$due_date <- as.character(as.Date(row$filing_date) + rule$statutory_days)
        row$not_filed_reason <- ""
      } else {
        if (!nzchar(row$not_filed_reason)) stop("Missing reason for failed filing")
        filing_fields <- c(
          "filing_date", "registration_number", "payment_reference",
          "due_date", "fee_paid_inr", "payment_mode"
        )
        for (field in filing_fields) row[[field]] <- ""
      }
      fields <- setdiff(names(row), c("application_id", "timestamp", "source_row_id"))
      fields <- intersect(fields, names(state$applications))
      state$applications[target, fields] <- row[fields]
    } else {
      for (field in c("event_type", "medium")) row[[field]] <- coerce_choice(row[[field]], field, vocab)
      if (!nzchar(row$event_type)) stop("Missing event type")
      validate_date(row$event_date)
      row$event_id <- as.character(nrow(state$events) + 1L)
      row$direction <- ifelse(row$event_type %in% vocab$outbound_event_types, "outbound", "inbound")
      row$recorded_at <- row$timestamp
      state$events <- dplyr::bind_rows(state$events, row[names(state$events)])
    }
    state$submissions <- dplyr::bind_rows(state$submissions, data.frame(
      source_row_id = row$source_row_id,
      form = form, application_id = row$application_id, timestamp = row$timestamp, payload_sha256 = payload
    ))
  }
  state
}

sync_intake <- function(state, issued) {
  assert_key(issued, "application_id")
  if (any(!state$applications$application_id %in% issued$application_id)) {
    stop("Intake contains unregistered applications")
  }
  added <- issued[!issued$application_id %in% state$applications$application_id, ]
  if (nrow(added)) state$applications <- dplyr::bind_rows(state$applications, new_intake(added)$applications)
  state
}
