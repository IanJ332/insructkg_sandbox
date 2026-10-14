.PHONY: check install init start start-pl start-dashboard seed graph test test-sql test-feedback evaluate fresh-preflight stop reset demo smoke test-public test-research quality build e2e
check install init start start-pl start-dashboard seed graph test test-sql test-feedback evaluate fresh-preflight stop reset demo smoke test-public test-research quality build e2e:
	python3 scripts/manage.py $@
