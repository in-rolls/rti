source("scripts/00_config.R")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L || !args[1] %in% c("filing", "update")) {
  stop("Usage: Rscript scripts/intake.R filing|update EXPORT.csv")
}
path <- file.path(project_root, "data", "private", "intake.rds")
if (file.exists(path)) {
  state <- readRDS(path)
} else {
  state <- new_intake(read_issued_assignments())
}
state <- sync_intake(state, read_issued_assignments())
rules <- yaml::read_yaml(file.path(project_root, "config", "state_rules.yaml"))$states
updated <- apply_form(state, read_form(read_csv_text(args[2]), args[1]), args[1], rules)
save_rds_atomic(updated, path)
message(nrow(updated$submissions) - nrow(state$submissions), " new submissions")
