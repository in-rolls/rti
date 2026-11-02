project_root <- normalizePath(Sys.getenv("RTI_ROOT", unset = "."), mustWork = TRUE)
if (!file.exists(file.path(project_root, "DESCRIPTION"))) stop("Run from the project root or set RTI_ROOT")
for (module in c("io", "frames", "collect", "sampling", "intake", "letters", "release", "privacy")) {
  source(file.path(project_root, "R", paste0(module, ".R")))
}
vocabularies <- jsonlite::read_json(file.path(project_root, "config", "vocabularies.json"), simplifyVector = TRUE)
