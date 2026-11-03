fetch_portal <- function(url) {
  httr2::request(url) |>
    httr2::req_user_agent("in-rolls/rti research frame collection (https://github.com/in-rolls/rti)") |>
    httr2::req_timeout(60) |>
    httr2::req_retry(max_tries = 5, retry_on_failure = TRUE) |>
    httr2::req_perform() |>
    httr2::resp_body_string()
}

parse_tn_rows <- function(html, page_url = "https://rtionline.tn.gov.in/displayPa.php") {
  document <- xml2::read_html(html)
  rows <- xml2::xml_find_all(document, "//table//tr[count(td) >= 3]")
  parsed <- lapply(rows, function(row) {
    cells <- xml2::xml_find_all(row, "./td")
    if (!grepl("^[0-9]+$", normalize_text(xml2::xml_text(cells[1])))) {
      return(NULL)
    }
    selector <- ".//div[contains(concat(' ', normalize-space(@class), ' '), ' text-primary ')]"
    primary <- xml2::xml_find_first(cells[[2]], selector)
    has_primary <- !inherits(primary, "xml_missing")
    name <- xml2::xml_text(if (has_primary) primary else cells[[2]])
    address <- if (has_primary) xml2::xml_text(xml2::xml_find_first(primary, "following-sibling::div[1]")) else ""
    link <- xml2::xml_find_first(cells[[length(cells)]], ".//a[contains(@href, 'show_sub_office')]")
    href <- xml2::xml_attr(link, "href")
    data.frame(
      office_name = normalize_text(name), address = normalize_text(address),
      url = ifelse(is.na(href), "", xml2::url_absolute(href, page_url)), is_leaf = is.na(href)
    )
  })
  dplyr::bind_rows(parsed)
}

collect_tn <- function(directory, fetch = fetch_portal, pause = 1) {
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  manifest_path <- file.path(directory, "crawl.rds")
  queue <- if (file.exists(manifest_path)) {
    readRDS(manifest_path)
  } else {
    data.frame(
      node_id = "displayPa", parent_id = "", office_name = "TAMIL NADU (ROOT)", address = "", depth = 0L,
      path = "", url = "https://rtionline.tn.gov.in/displayPa.php", is_leaf = FALSE, fetched = FALSE
    )
  }
  while (any(!queue$fetched & !queue$is_leaf)) {
    i <- which(!queue$fetched & !queue$is_leaf)[1]
    file <- file.path(directory, paste0(queue$node_id[i], ".html"))
    if (!file.exists(file)) {
      html <- fetch(queue$url[i])
      if (!grepl("<table", html, ignore.case = TRUE)) stop("Portal returned no office table: ", queue$node_id[i])
      parsed <- parse_tn_rows(html, queue$url[i])
      if (!nrow(parsed) || any(!nzchar(parsed$office_name))) stop("No recognizable office rows; crawl incomplete")
      writeLines(html, file, useBytes = TRUE)
      if (pause > 0) Sys.sleep(pause)
    }
    children <- parse_tn_rows(paste(readLines(file, warn = FALSE), collapse = "\n"), queue$url[i])
    if (!nrow(children)) stop("Cached page has no recognizable offices; crawl incomplete")
    if (nrow(children)) {
      paths <- children$office_name
      if (nzchar(queue$path[i])) paths <- paste(queue$path[i], paths, sep = " > ")
      keys <- ifelse(children$is_leaf,
        paste(queue$node_id[i], toupper(children$office_name), toupper(children$address), sep = "|"), toupper(paths)
      )
      children <- data.frame(
        node_id = hash_text(keys, 16L, "sha1"), parent_id = queue$node_id[i],
        office_name = children$office_name, address = children$address, depth = queue$depth[i] + 1L,
        path = paths, url = children$url, is_leaf = children$is_leaf, fetched = FALSE
      )
      queue <- dplyr::bind_rows(queue, children[!duplicated(children$node_id) & !children$node_id %in% queue$node_id, ])
    }
    queue$fetched[i] <- TRUE
    save_rds_atomic(queue, manifest_path)
  }
  queue
}
