source("scripts/00_config.R")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Usage: Rscript scripts/render_batch.R BATCH_DIRECTORY FILER.yaml")
metadata <- jsonlite::read_json(file.path(args[1], "metadata.json"), simplifyVector = TRUE)
config <- metadata$config
assignments <- read_csv_text(file.path(args[1], "assignments.csv"))
filer <- yaml::read_yaml(args[2])
directory <- file.path(project_root, "data", "private", "letters", config$batch_id)
render_batch_letters(assignments, config, filer, directory)
