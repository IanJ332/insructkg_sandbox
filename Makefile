.PHONY: check install init start start-pl start-dashboard seed graph test test-sql test-feedback evaluate fresh-preflight stop reset demo smoke
check install init start start-pl start-dashboard seed graph test test-sql test-feedback evaluate fresh-preflight stop reset demo smoke:
	python3 scripts/manage.py $@
