parse_department_group <- function(office, state_code) {
  if (state_code == "KA") {
    group <- sub(".*-", "", office)
    group <- sub(".*,", "", group)
  } else {
    group <- sub("[(,].*", "", office)
  }
  group <- stringr::str_to_upper(group)
  group <- gsub("&", " AND ", group, fixed = TRUE)
  group <- trimws(normalize_text(group), whitespace = "[ .-]")
  if (state_code == "KA") group <- sub("^(DEPARTMENT|DEPT\\.?)\\s+OF\\s+", "", group)
  group <- sub("\\s+(DEPARTMENT|DEPT\\.?)$", "", group)
  ifelse(nzchar(group), group, "UNKNOWN")
}

parse_portal_names <- function(path, state_code) {
  if (state_code == "TG") {
    paths <- list.files(path, pattern = "^page_[0-9]+\\.json$", full.names = TRUE)
    if (!length(paths)) stop("No Telangana portal pages")
    names <- unlist(lapply(paths, function(page) {
      text <- paste(readLines(page, warn = FALSE), collapse = " ")
      jsonlite::fromJSON(gsub("[[:cntrl:]]", " ", text))
    }), use.names = FALSE)
    return(data.frame(office_name = sort(unique(normalize_text(names)), method = "radix"), portal_value_id = ""))
  }
  document <- xml2::read_html(path)
  if (state_code == "KA") {
    rows <- xml2::xml_find_all(document, "//tr[count(td|th) >= 2]")
    names <- vapply(rows[-1], function(row) {
      normalize_text(xml2::xml_text(xml2::xml_find_first(row, "./td[2]|./th[2]")))
    }, character(1))
    names <- names[nzchar(names) & !is.na(names)]
    return(data.frame(office_name = sort(unique(names), method = "radix"), portal_value_id = ""))
  }
  html <- paste(readLines(path, warn = FALSE), collapse = "\n")
  select <- stringr::str_match(html, "(?is)<select[^>]*(?:name|id)=\"MinistryId\"[^>]*>(.*?)</select>")[, 2]
  if (is.na(select)) stop("MinistryId select not found")
  options <- stringr::str_match_all(select, "(?s)<option[^>]*value=\"([^\"]*)\"[^>]*>(.*?)</option>")[[1]]
  names <- normalize_text(gsub("<[^>]+>", " ", options[, 3]))
  values <- normalize_text(options[, 2])
  keep <- nzchar(names) & nzchar(values) & !grepl("--Select--", names, fixed = TRUE)
  result <- data.frame(office_name = names[keep], portal_value_id = values[keep])
  result <- result[order(result$office_name, method = "radix"), ]
  result[!duplicated(gsub("[^a-z0-9]", "", tolower(result$office_name))), ]
}

build_flat_frame <- function(path, legacy_path, state_code, state, portal) {
  frame <- parse_portal_names(path, state_code)
  legacy <- read_csv_text(legacy_path)
  if ("State" %in% names(legacy)) legacy <- legacy[legacy$State == state, ]
  match_key <- function(text) gsub("[^a-z0-9]", "", tolower(text))
  # Earlier scripts retain the last legacy row for a duplicate normalized name.
  legacy <- legacy[!duplicated(match_key(legacy$Department), fromLast = TRUE), ]
  matches <- match(match_key(frame$office_name), match_key(legacy$Department))
  district <- dplyr::coalesce(legacy$District[matches], "")
  block <- dplyr::coalesce(legacy$Block[matches], "")
  if (state_code == "KA") {
    guessed <- trimws(sub("\\s*-.*", "", frame$office_name))
    guessed[nchar(guessed) > 30 | grepl(",", guessed, fixed = TRUE)] <- ""
    district[is.na(matches)] <- guessed[is.na(matches)]
  }
  data.frame(
    State = state, Department = frame$office_name, Website = portal,
    District = district, Block = block, portal_value_id = frame$portal_value_id
  )
}

normalize_frame <- function(frame, state_code) {
  if (state_code == "TN") {
    frame <- frame[frame$state == "Tamil Nadu", ]
    return(dplyr::transmute(frame, authority_id, state, state_code,
      office_name = department,
      district, block, portal, node_id, tree_department, tier = level_label,
      dept_group = tree_department
    ))
  }
  office <- frame$Department
  state <- frame$State
  ids <- make_authority_id(state, office, frame$District, frame$Block)
  occurrence <- ave(seq_along(ids), ids, FUN = seq_along)
  data.frame(
    authority_id = make_authority_id(state, office, frame$District, frame$Block, occurrence),
    state = state, state_code = state_code, office_name = office,
    district = frame$District, block = frame$Block, portal = frame$Website,
    node_id = "", tree_department = "", tier = "", dept_group = parse_department_group(office, state_code)
  )
}

build_frames <- function(root = project_root) {
  definitions <- yaml::read_yaml(file.path(root, "config", "sources.yaml"))
  frames <- list()
  for (code in names(definitions)) {
    definition <- definitions[[code]]
    frozen <- read_csv_text(file.path(root, definition$frozen))
    if (code == "TN") {
      rebuilt <- build_tn_frame(root)
      expected <- normalize_frame(frozen, code)
      rebuilt <- rebuilt[match(expected$authority_id, rebuilt$authority_id), ]
      if (!isTRUE(all.equal(as.data.frame(rebuilt), as.data.frame(expected), check.attributes = FALSE))) {
        stop("Rebuilt frame differs from frozen frame: TN")
      }
      frames[[code]] <- rebuilt
      next
    } else {
      frame <- build_flat_frame(
        file.path(root, definition$raw), file.path(root, definition$legacy),
        code, definition$state, definition$portal
      )
      expected <- frozen[frozen$State == definition$state, ]
      frame <- frame[, names(expected), drop = FALSE]
      if (!isTRUE(all.equal(as.data.frame(frame), as.data.frame(expected), check.attributes = FALSE))) {
        stop("Rebuilt frame differs from frozen frame: ", code)
      }
    }
    frames[[code]] <- normalize_frame(frame, code)
  }
  result <- dplyr::bind_rows(frames)
  assert_key(result, "authority_id")
  result
}

clean_office_text <- function(value) {
  value <- normalize_text(value)
  value <- sub('^"(.*)"$', "\\1", value)
  gsub('(?<=[A-Za-z])"(?=[A-Za-z])', "'", value, perl = TRUE)
}

build_tn_frame <- function(root) {
  tree <- read_csv_text(file.path(root, "data", "reference", "tn", "universe_categorized.csv"))
  legacy <- read_csv_text(file.path(root, "data", "raw", "tn", "state_department_classified_FINAL.csv"))
  legacy <- legacy[legacy$State == "Tamil Nadu", ]
  join_key <- function(names) {
    key <- normalize_key(clean_office_text(names))
    paste(key, ave(seq_along(key), key, FUN = seq_along), sep = "|")
  }
  matches <- match(join_key(tree$name), join_key(legacy$Department))
  if (nrow(tree) != nrow(legacy) || anyNA(matches) || anyDuplicated(matches)) {
    stop("TN classification join is not one-to-one")
  }
  clean_location <- function(value) {
    value <- clean_office_text(value)
    value[toupper(value) %in% c("NA", "N/A", "NIL", "NONE", "-")] <- ""
    value
  }
  data.frame(
    authority_id = paste0("TN-", tree$node_id), state = "Tamil Nadu", state_code = "TN",
    office_name = clean_office_text(tree$name), district = clean_location(legacy$District[matches]),
    block = clean_location(legacy$Block[matches]), portal = "rti_tamil_nadu", node_id = tree$node_id,
    tree_department = clean_office_text(tree$department), tier = clean_office_text(tree$level_label),
    dept_group = clean_office_text(tree$department)
  )
}
