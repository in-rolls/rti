filing_fixture <- function() {
  read_form(data.frame(
    Timestamp = c("2026-01-01 12:00", "2026-01-01 13:00"),
    `Application ID` = "TN-001", Outcome = "filed", `Date filed` = "2026-01-01",
    `Registration number` = c("FIRST", "SECOND"), `Payment mode` = "online", check.names = FALSE
  ), "filing")
}

intake_fixture <- function() new_intake(data.frame(application_id = "TN-001", state = "Tamil Nadu"))
intake_rules <- list(`_default` = list(statutory_days = 30L))

testthat::test_that("replaying multiple submissions preserves a reviewed correction", {
  rows <- filing_fixture()
  state <- apply_form(intake_fixture(), rows, "filing", intake_rules)
  testthat::expect_equal(state$applications$registration_number, "SECOND")
  state$applications$registration_number <- "MANUAL"
  replayed <- apply_form(state, rows, "filing", intake_rules)
  testthat::expect_identical(replayed, state)
  single <- rows[2, ]
  rownames(single) <- NULL
  testthat::expect_identical(apply_form(state, single, "filing", intake_rules), state)
  rows$registration_number[1] <- "CHANGED"
  testthat::expect_error(apply_form(state, rows, "filing", intake_rules), "submission changed")
})

testthat::test_that("filing transitions clear incompatible fields in both directions", {
  rows <- filing_fixture()[1, ]
  state <- apply_form(intake_fixture(), rows, "filing", intake_rules)
  testthat::expect_equal(state$applications$due_date, "2026-01-31")
  rows$timestamp <- "2026-01-02"
  rows$filing_outcome <- "not_filed"
  rows$not_filed_reason <- "portal_down"
  state <- apply_form(state, rows, "filing", intake_rules)
  for (field in c("filing_date", "registration_number", "due_date", "payment_reference", "payment_mode")) {
    testthat::expect_equal(state$applications[[field]], "")
  }
  rows$timestamp <- "2026-01-03"
  rows$filing_outcome <- "filed"
  state <- apply_form(state, rows, "filing", intake_rules)
  testthat::expect_equal(state$applications$not_filed_reason, "")
  testthat::expect_equal(state$applications$due_date, "2026-01-31")
})

testthat::test_that("invalid exports fail without mutating caller state", {
  rows <- filing_fixture()
  state <- intake_fixture()
  rows$application_id[2] <- "TN-999"
  testthat::expect_error(apply_form(state, rows, "filing", intake_rules), "Unknown application")
  testthat::expect_equal(nrow(state$submissions), 0L)
  rows <- filing_fixture()
  rows$payment_mode[2] <- "unknown option"
  testthat::expect_error(apply_form(state, rows, "filing", intake_rules), "Unrecognized")
  testthat::expect_equal(state$applications$filing_outcome, "")
})

testthat::test_that("repeated events append once per source submission", {
  rows <- read_form(data.frame(
    Timestamp = c("one", "two"), `Application ID` = "TN-001",
    `What happened` = "response_received", `Date` = "2026-01-31", `Medium` = "email", check.names = FALSE
  ), "update")
  state <- apply_form(intake_fixture(), rows, "update", intake_rules)
  testthat::expect_equal(nrow(state$events), 2L)
  testthat::expect_identical(apply_form(state, rows, "update", intake_rules), state)
})

testthat::test_that("existing form labels remain recognized", {
  testthat::expect_equal(coerce_choice("Could not file", "filing_outcome"), "not_filed")
})
