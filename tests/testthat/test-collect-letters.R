testthat::test_that("TN parser distinguishes clickable nodes and leaves", {
  html <- paste0(
    '<table><tr><td>1</td><td><div class="text-primary">Office A</div>',
    '<div>Address A</div></td><td><a href="show_sub_office.php?min_code=abc">View</a></td></tr>',
    "<tr><td>2</td><td>Office B</td><td>No Suboffices Currently Onboarded</td></tr></table>"
  )
  rows <- parse_tn_rows(html)
  testthat::expect_equal(rows$office_name, c("Office A", "Office B"))
  testthat::expect_equal(rows$is_leaf, c(FALSE, TRUE))
  testthat::expect_equal(rows$address, c("Address A", ""))
  testthat::expect_match(rows$url[1], "^https://rtionline.tn.gov.in/show_sub_office")
})

testthat::test_that("crawler checkpoints and resumes without refetching", {
  path <- tempfile()
  on.exit(unlink(path, recursive = TRUE))
  calls <- 0L
  fetch <- function(url) {
    calls <<- calls + 1L
    "<table><tr><td>1</td><td>Office A</td><td>No Suboffices Currently Onboarded</td></tr></table>"
  }
  first <- collect_tn(path, fetch, pause = 0)
  second <- collect_tn(path, fetch, pause = 0)
  testthat::expect_equal(calls, 1L)
  testthat::expect_identical(first, second)
  testthat::expect_equal(nrow(first), 2L)
})

testthat::test_that("letter rendering requires fields and treats values literally", {
  testthat::expect_equal(render_letter("Dear {name}: {text}", list(name = "A", text = "$1 \\1")), "Dear A: $1 \\1")
  testthat::expect_error(render_letter("{missing}", list()), "Missing")
})

testthat::test_that("a login table cannot become a successful crawl checkpoint", {
  path <- tempfile()
  on.exit(unlink(path, recursive = TRUE))
  fetch <- function(url) "<table><tr><td>Please sign in</td></tr></table>"
  testthat::expect_error(collect_tn(path, fetch, pause = 0), "recognizable office")
  testthat::expect_length(list.files(path), 0L)
})

testthat::test_that("batch rendering inserts only the assigned treatment and fills the instrument", {
  config <- yaml::read_yaml(file.path(project_root, "config", "example_batch.yaml"))
  filer <- yaml::read_yaml(file.path(project_root, "config", "filer.example.yaml"))
  assignments <- data.frame(
    application_id = c("KA-181", "KA-182"), office_name = "Example Office",
    assigned_ra = "RA1", treatment = c("plain", "legal_salience")
  )
  directory <- tempfile()
  on.exit(unlink(directory, recursive = TRUE))
  paths <- render_batch_letters(assignments, config, filer, directory)
  text <- vapply(paths, function(path) paste(readLines(path), collapse = "\n"), character(1))
  legal <- paste(readLines(file.path(project_root, config$legal_salience)), collapse = "\n")
  testthat::expect_false(grepl(legal, text[1], fixed = TRUE))
  testthat::expect_true(grepl(legal, text[2], fixed = TRUE))
  testthat::expect_false(any(grepl("\\{[A-Za-z_]", text)))
  testthat::expect_true(all(grepl("Example Office", text, fixed = TRUE)))
  testthat::expect_error(render_letter("{fy1}", list()), "Missing")
})
