source("scripts/00_config.R")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) stop("Usage: Rscript scripts/collect_tn.R PRIVATE_CRAWL_DIRECTORY")
collect_tn(args[1])
