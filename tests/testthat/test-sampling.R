testthat::test_that("allocation honors totals, floors, capacity and ties", {
  testthat::expect_equal(allocate_counts(c(a = 4, b = 3, c = 2), 4), c(a = 2L, b = 1L, c = 1L))
  testthat::expect_equal(allocate_counts(c(a = 9, b = 1), 5, capacity = c(3, 2)), c(a = 3L, b = 2L))
  testthat::expect_equal(allocate_counts(c(a = 1, b = 1, c = 1), 2), c(a = 1L, b = 1L, c = 0L))
  testthat::expect_equal(sum(allocate_counts(c(a = 5, b = 8), 10, minimum = c(4, 4))), 10)
  testthat::expect_error(allocate_counts(c(a = 1), 2), "Infeasible")
  testthat::expect_error(allocate_counts(c(a = 0), 1, capacity = 2), "positive-weight")
})

testthat::test_that("new draws exclude issued offices, preserve IDs and balance treatment", {
  frame <- data.frame(
    authority_id = sprintf("office-%03d", 1:100), state_code = "KA", state = "Karnataka",
    dept_group = rep(c("A", "B"), each = 50), office_name = sprintf("Office %03d", 1:100)
  )
  issued <- data.frame(application_id = "KA-180", authority_id = frame$authority_id[1])
  config <- list(
    template_version = "test-v1", language = "en", channel = "portal",
    engine = "r-v1", batch_id = "test", seed = 22, state_codes = "KA",
    sampling = list(strategy = "proportional", sample_size = 40, cap = 30, minimum = 1),
    treatment = list(n_legal = 12, blocks = "dept_group"), assistants = c("RA1", "RA2", "RA3", "RA4")
  )
  one <- draw_batch(frame, config, issued)
  two <- draw_batch(frame[100:1, ], config, issued)
  testthat::expect_equal(one$assignments, two$assignments)
  testthat::expect_false(issued$authority_id %in% one$assignments$authority_id)
  testthat::expect_equal(sum(one$assignments$treatment == "legal_salience"), 12L)
  testthat::expect_equal(sort(as.integer(table(one$assignments$assigned_ra))), rep(10L, 4))
  testthat::expect_equal(one$assignments$application_id[1], "KA-181")
  testthat::expect_equal(nrow(one$assignments), 40L)
  config$engine <- "python-historical"
  testthat::expect_error(draw_batch(frame, config, issued), "historical")
})

testthat::test_that("tier quotas retain headquarters and refill only sub-offices", {
  frame <- data.frame(
    authority_id = as.character(1:16), dept_group = rep(c("A", "B"), each = 8),
    tier = rep(c("Department", "Head of Department", rep("Sub Office", 6)), 2)
  )
  design <- list(
    strategy = "department_tier_quotas", sample_size = 12,
    quotas = list(Department = 1, `Head of Department` = 1, `Sub Office` = 2), refill_tier = "Sub Office"
  )
  selected <- select_offices(frame, design)
  testthat::expect_equal(nrow(selected), 12L)
  testthat::expect_equal(sum(selected$tier == "Department"), 2L)
  testthat::expect_equal(sum(selected$tier == "Sub Office"), 8L)
  testthat::expect_equal(length(unique(selected$authority_id)), 12L)
})

testthat::test_that("assistant workloads balance across nondivisible treatment arms", {
  rows <- data.frame(treatment = c(rep("legal_salience", 3), rep("plain", 7)), randomization_stratum = "batch")
  assigned <- assign_assistants(rows, c("RA1", "RA2", "RA3", "RA4"))
  loads <- table(assigned$assigned_ra)
  testthat::expect_lte(max(loads) - min(loads), 1L)
})

testthat::test_that("missing headquarters cannot silently be replaced by sub-offices", {
  frame <- data.frame(authority_id = c("a", "b"), dept_group = "A", tier = "Sub Office")
  design <- list(
    strategy = "department_tier_quotas", sample_size = 2,
    quotas = list(Department = 1, `Sub Office` = 1), refill_tier = "Sub Office"
  )
  testthat::expect_error(select_offices(frame, design), "certainty tier")
})

testthat::test_that("registration rejects reused IDs and offices and intake adds issued rows", {
  issued <- data.frame(application_id = "KA-001", authority_id = "old", batch_id = "old", state = "Karnataka")
  rows <- data.frame(
    application_id = "KA-002", authority_id = "new", batch_id = "new", state = "Karnataka",
    template_version = "v1", language = "en", channel = "portal", assigned_ra = "RA1", treatment = "plain"
  )
  testthat::expect_silent(register_batch(list(assignments = rows), issued))
  testthat::expect_error(register_batch(list(assignments = rows), rows), "conflicts")
  state <- new_intake(issued)
  state$applications$notes <- "Reviewed correction"
  synced <- sync_intake(state, dplyr::bind_rows(issued, rows))
  testthat::expect_equal(synced$applications$application_id, c("KA-001", "KA-002"))
  testthat::expect_equal(synced$applications$notes, c("Reviewed correction", ""))
})

testthat::test_that("publishing a registered batch preserves one copy and rejects changed records", {
  rows <- dplyr::tibble(
    application_id = c("KA-181", "KA-182"), authority_id = c("a", "b"),
    batch_id = "new", treatment = c("plain", "legal_salience"), assigned_ra = "RA1"
  )
  batches <- list(new = list(assignments = rows))
  testthat::expect_equal(combine_issued_assignments(rows[2:1, ], batches), rows[2:1, ])
  testthat::expect_equal(combine_issued_assignments(rows[FALSE, ], batches), rows)
  changed <- rows
  changed$treatment[1] <- "legal_salience"
  testthat::expect_error(combine_issued_assignments(changed, batches), "differs")
  testthat::expect_error(combine_issued_assignments(rows[1, ], batches), "differs")
  testthat::expect_error(combine_issued_assignments(rows[, -5], batches), "differs")
  changed <- rows
  changed$batch_id <- "different"
  testthat::expect_error(combine_issued_assignments(changed, batches), "duplicate key")
})
