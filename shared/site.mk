# ember — Jekyll GitHub Pages site (site/)
#
# The site is assembled from the repository's own markdown by
# scripts/build_site_docs.py, then built with Jekyll. Jekyll runs in Docker
# because the macOS system Ruby (2.6) is too old for Jekyll 4; CI uses
# ruby/setup-ruby. Pages is deployed by .github/workflows/deploy-site.yml.

SITE_DIR := $(CURDIR)/site
JEKYLL_IMAGE := ruby:3.3-bookworm
JEKYLL_DOCKER := docker run --rm --user "$$(id -u):$$(id -g)" \
	-e HOME=/tmp -e GEM_HOME=/tmp/gems -e BUNDLE_PATH=/tmp/gems \
	-e BUNDLE_USER_CONFIG=/tmp/bundle-config \
	-v "$(SITE_DIR)/.gems":/tmp/gems -v "$(SITE_DIR)":/srv/jekyll -w /srv/jekyll

.PHONY: site site-serve

site: ## Build the Pages site into site/_site (needs Docker)
	@mkdir -p "$(SITE_DIR)/.gems"
	$(PY) scripts/build_site_docs.py
	$(PY) scripts/build_site_benchmark.py
	$(JEKYLL_DOCKER) $(JEKYLL_IMAGE) bash -lc 'bundle install --quiet && bundle exec jekyll build --baseurl ""'
	@echo "built: $(SITE_DIR)/_site"

site-serve: ## Preview the Pages site at http://localhost:4000 (needs Docker)
	@mkdir -p "$(SITE_DIR)/.gems"
	$(PY) scripts/build_site_docs.py
	$(PY) scripts/build_site_benchmark.py
	$(JEKYLL_DOCKER) -p 4000:4000 $(JEKYLL_IMAGE) bash -lc 'bundle install --quiet && bundle exec jekyll serve --host 0.0.0.0 --baseurl ""'
