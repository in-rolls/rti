allocate_counts <- function(weights, total, capacity = weights, minimum = rep(0L, length(weights))) {
  if (length(total) != 1L || !is.finite(total)) stop("Invalid allocation total")
  if (is.null(names(weights)) || anyDuplicated(names(weights))) stop("Allocation groups must have unique names")
  invalid_lengths <- length(capacity) != length(weights) || length(minimum) != length(weights)
  invalid_values <- any(!is.finite(c(weights, capacity, minimum, total))) || any(weights < 0)
  invalid_bounds <- any(minimum < 0 | minimum > capacity) || any(c(capacity, minimum, total) %% 1 != 0)
  if (invalid_lengths || invalid_values || invalid_bounds || total < sum(minimum) || total > sum(capacity)) {
    stop("Infeasible allocation")
  }
  allocated <- setNames(as.integer(minimum), names(weights))
  while (sum(allocated) < total) {
    open <- which(allocated < capacity & weights > 0)
    if (!length(open)) stop("No positive-weight capacity remains")
    quota <- weights[open] / sum(weights[open]) * (total - sum(allocated))
    increment <- pmin(floor(quota), capacity[open] - allocated[open])
    allocated[open] <- allocated[open] + increment
    available <- which(allocated[open] < capacity[open])
    remainder_order <- order(-(quota[available] - floor(quota[available])),
      names(weights)[open[available]],
      method = "radix"
    )
    extra <- open[available[head(remainder_order, total - sum(allocated))]]
    allocated[extra] <- allocated[extra] + 1L
  }
  allocated
}

sample_rows <- function(rows, n) {
  if (n > nrow(rows) || n < 0) stop("Insufficient offices for requested sample")
  rows[sample.int(nrow(rows), n), , drop = FALSE]
}

assign_treatments <- function(rows, n_legal, blocks = character()) {
  strata <- if (length(blocks)) do.call(paste, c(rows[blocks], sep = " | ")) else rep("batch", nrow(rows))
  sizes <- table(strata)
  counts <- allocate_counts(sizes, n_legal)
  rows$treatment <- "plain"
  for (stratum in names(counts)) {
    indices <- which(strata == stratum)
    chosen <- indices[sample.int(length(indices), counts[[stratum]])]
    rows$treatment[chosen] <- "legal_salience"
  }
  rows$randomization_stratum <- strata
  rows
}

assign_assistants <- function(rows, assistants) {
  if (!length(assistants) || anyDuplicated(assistants) || any(!nzchar(assistants))) stop("Invalid assistants")
  rows$assigned_ra <- ""
  cursor <- 0L
  for (arm in sort(unique(rows$treatment))) {
    for (stratum in sort(unique(rows$randomization_stratum), method = "radix")) {
      indices <- which(rows$treatment == arm & rows$randomization_stratum == stratum)
      indices <- indices[sample.int(length(indices))]
      rows$assigned_ra[indices] <- assistants[(cursor + seq_along(indices) - 1L) %% length(assistants) + 1L]
      cursor <- cursor + length(indices)
    }
  }
  rows
}

select_offices <- function(frame, design) {
  if (design$strategy == "department_tier_quotas") {
    quotas <- unlist(design$quotas)
    if (any(!unique(frame$tier) %in% names(quotas))) stop("Unconfigured office tier")
    certainty_tiers <- if (is.null(design$certainty_tiers)) "Department" else unlist(design$certainty_tiers)
    sizes <- table(frame$dept_group, factor(frame$tier, levels = names(quotas)))
    for (tier in certainty_tiers) {
      if (!tier %in% names(quotas) || any(sizes[, tier] != quotas[[tier]])) stop("Invalid certainty tier: ", tier)
    }
    pieces <- split(frame, interaction(frame$dept_group, frame$tier, drop = TRUE, lex.order = TRUE))
    selected <- dplyr::bind_rows(lapply(pieces, function(rows) {
      sample_rows(rows, min(nrow(rows), quotas[[rows$tier[1]]]))
    }))
    if (nrow(selected) > design$sample_size) stop("Tier quotas exceed target")
    remaining <- frame[frame$tier == design$refill_tier & !frame$authority_id %in% selected$authority_id, ]
    return(dplyr::bind_rows(selected, sample_rows(remaining, design$sample_size - nrow(selected))))
  }
  if (design$strategy != "proportional") stop("Unknown sampling strategy")
  sizes <- table(frame$dept_group)
  capacity <- pmin(sizes, if (is.null(design$cap)) Inf else design$cap)
  minimum <- pmin(capacity, if (is.null(design$minimum)) 0L else design$minimum)
  counts <- allocate_counts(sizes, design$sample_size, capacity, minimum)
  dplyr::bind_rows(lapply(names(counts), function(group) {
    sample_rows(frame[frame$dept_group == group, ], counts[[group]])
  }))
}

draw_batch <- function(frame, config, issued = data.frame(application_id = character(), authority_id = character())) {
  assert_key(frame, "authority_id")
  if (!identical(config$engine, "r-v1")) {
    stop("Only new r-v1 batches may be drawn; verify historical assignments instead")
  }
  if (!length(config$state_codes) || is.null(config$seed) || is.null(config$batch_id)) {
    stop("Incomplete batch configuration")
  }
  previous_rng <- RNGkind()
  has_seed <- exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  if (has_seed) previous_seed <- get(".Random.seed", envir = .GlobalEnv)
  on.exit({
    do.call(RNGkind, as.list(previous_rng))
    if (has_seed) assign(".Random.seed", previous_seed, envir = .GlobalEnv) # nolint: object_name_linter.
    if (!has_seed) rm(list = ".Random.seed", envir = .GlobalEnv)
  })
  RNGkind("Mersenne-Twister", "Inversion", "Rejection")
  set.seed(config$seed)
  eligible <- frame[frame$state_code %in% config$state_codes & !frame$authority_id %in% issued$authority_id, ]
  eligible <- eligible[order(eligible$authority_id, method = "radix"), ]
  selected <- select_offices(eligible, config$sampling)
  selected <- selected[order(selected$state_code, selected$dept_group, selected$office_name, method = "radix"), ]
  selected <- assign_treatments(selected, config$treatment$n_legal, unlist(config$treatment$blocks))
  selected <- assign_assistants(selected, unlist(config$assistants))
  selected$application_id <- ""
  for (code in unique(selected$state_code)) {
    indices <- which(selected$state_code == code)
    start <- next_sequence(issued$application_id, code)
    selected$application_id[indices] <- make_application_id(code, start + seq_along(indices) - 1L)
  }
  selected$batch_id <- config$batch_id
  for (field in c("template_version", "language", "channel")) {
    if (is.null(config[[field]]) || !nzchar(config[[field]])) stop("Missing batch field: ", field)
    selected[[field]] <- config[[field]]
  }
  assert_key(selected, "application_id")
  list(assignments = selected, metadata = list(
    engine = config$engine, r_version = as.character(getRversion()),
    rng = RNGkind(), seed = config$seed, config = config,
    frame_sha256 = digest::digest(frame, algo = "sha256"),
    issued_sha256 = digest::digest(issued, algo = "sha256")
  ))
}
