.PHONY: install smoke regression sanity report clean

install:
	pip install -e ".[dev]"
	playwright install --with-deps chromium

smoke:
	pytest -m smoke -v --tb=short

regression:
	pytest -m regression -v --tb=short

sanity:
	pytest -m sanity -v --tb=short

report:
	phoenix report

generate:
	@echo "Usage: phoenix generate <user-story-file>"
	@ls user_stories/

clean:
	rm -rf .pytest_cache __pycache__ reports/*.html logs/*.jsonl
