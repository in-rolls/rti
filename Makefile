.PHONY: restore release site test lint format check ci-docker

restore:
	Rscript --vanilla -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org"); renv::load(project = getwd()); renv::restore(prompt = FALSE)'

release:
	Rscript scripts/01_build_release.R

site:
	Rscript scripts/02_build_site.R

test:
	Rscript -e 'testthat::test_dir("tests/testthat", stop_on_failure = TRUE)'

lint:
	Rscript -e 'lints <- unlist(lapply(c("R", "scripts", "tests"), lintr::lint_dir), recursive = FALSE); print(lints); quit(status = as.integer(length(lints) > 0))'

format:
	Rscript -e 'for (path in c("R", "scripts", "tests")) styler::style_dir(path)'

check: site test lint

ci-docker:
	docker run --rm -v "$(CURDIR):/project" -w /project \
		-v r_renv_cache:/root/.cache/R/renv \
		-e RENV_CONFIG_REPOS_OVERRIDE=https://packagemanager.posit.co/cran/latest \
		rocker/tidyverse:4.6.0 bash -c "make restore check"

.PHONY: privacy hooks
privacy:
	Rscript scripts/check_privacy.R

hooks:
	git config core.hooksPath hooks

check: privacy
