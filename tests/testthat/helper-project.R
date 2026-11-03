project_root <- normalizePath(file.path(testthat::test_path(), "..", ".."))
Sys.setenv(RTI_ROOT = project_root)
source(file.path(project_root, "scripts", "00_config.R"))
