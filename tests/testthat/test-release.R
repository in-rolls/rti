testthat::test_that("frozen evidence and all state frames survive migration", {
  testthat::expect_silent(verify_sources())
  frame <- build_frames()
  testthat::expect_equal(as.integer(table(frame$state)), c(223L, 1800L, 328L, 17417L, 3401L))
  assignments <- read_assignments(frame)
  testthat::expect_equal(nrow(assignments), 1665L)
  testthat::expect_equal(as.integer(table(assignments$state)), c(44L, 180L, 66L, 1000L, 375L))
  testthat::expect_false(anyDuplicated(assignments$application_id) > 0)
  catalog <- read_csv_text(file.path(project_root, "config", "batches.csv"))
  for (path in catalog$path) {
    frozen <- read_csv_text(file.path(project_root, path))
    matched <- assignments[match(frozen$application_id, assignments$application_id), names(frozen)]
    testthat::expect_equal(as.data.frame(matched), as.data.frame(frozen), ignore_attr = TRUE)
  }
})

testthat::test_that("authority identity is vectorized and distinguishes duplicate offices", {
  ids <- make_authority_id("Tamil Nadu", c("One", "Two"))
  testthat::expect_length(unique(ids), 2L)
  testthat::expect_equal(ids[1], make_authority_id(" TAMIL NADU ", " one "))
  testthat::expect_false(identical(ids[1], make_authority_id("Tamil Nadu", "One", occurrence = 2)))
})

testthat::test_that("public worklists discard private data even with unrecognized fields", {
  rows <- data.frame(
    application_id = "TN-001", office_name = "Office", registration_number = "SECRET",
    filed_by = "Person", notes = "email@example.org", new_private_field = "secret"
  )
  public <- public_assignments(rows)
  testthat::expect_named(public, c("application_id", "office_name"))
  testthat::expect_error(check_public_assignments(rows), "Private")
})

testthat::test_that("every issued treatment and version has a preserved instrument", {
  assignments <- read_assignments(build_frames())
  instruments <- read_csv_text(file.path(project_root, "config", "instruments.csv"))
  key <- function(rows) paste(rows$batch_id, rows$template_version, rows$treatment, sep = "|")
  testthat::expect_setequal(key(assignments), key(instruments))
  testthat::expect_true(all(file.exists(file.path(project_root, "data", "reference", "batches", instruments$path))))
  tn <- assignments[assignments$state_code == "TN", ]
  paths <- file.path(
    project_root, "data", "reference", "batches", tn$batch_id, "applications",
    tn$assigned_ra, paste0(tn$application_id, ".txt")
  )
  testthat::expect_true(all(file.exists(paths)))
})

testthat::test_that("contact details inside allowed fields fail public validation", {
  rows <- data.frame(application_id = "KA-001", office_name = "Office meera@example.org")
  testthat::expect_error(public_assignments(rows), "Contact details")
  testthat::expect_true(contains_contact_details("Call 9800000123"))
})

testthat::test_that("worklist writer enforces the public boundary itself", {
  directory <- tempfile()
  on.exit(unlink(directory, recursive = TRUE))
  rows <- data.frame(
    application_id = "KA-001", assigned_ra = "RA1", registration_number = "SECRET",
    notes = "private", office_name = "Office"
  )
  write_worklists(rows, directory)
  written <- read_csv_text(file.path(directory, "RA1.csv"))
  testthat::expect_false(any(c("registration_number", "notes") %in% names(written)))
})
