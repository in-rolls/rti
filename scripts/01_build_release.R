source("scripts/00_config.R")
release <- build_release()
message(nrow(release$assignments), " issued assignments; ", nrow(release$authorities), " authorities")
