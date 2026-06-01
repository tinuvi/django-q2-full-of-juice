# SDLC rules

Imperative guidance for working on the project. Follow these end-to-end on every change.

## Code style

- Write a test for every implementation change. No exception for "trivial" fixes.
- Use parameterized logging only: `_logger.info("Message %s", value)`. Do **not** pre-format log strings with f-strings, `%`, or `.format()`.
- When you see `getLogger(__name__)`, change it to `getLogger("django_q")`.
- This project is **not type-annotated** and runs no static type checker. Don't add `pyrefly`/`mypy` unless the user asks.

## Updating poetry settings

- Update `poetry.lock` when `pyproject.toml` changes:
    ```bash
    docker compose -f test-services-docker-compose.yaml run --rm --remove-orphans integration-tests poetry update
    ```
- Build the Docker images to reflect the changes:
    ```bash
    docker compose -f test-services-docker-compose.yaml build integration-tests lint-formatter
    ```

## Testing

- **Selective runs**: replace `<test_module>` with the dotted path of the test module you want to run (e.g. `tests.test_cluster`):
    ```bash
    docker compose -f test-services-docker-compose.yaml run --remove-orphans --rm integration-tests bash -c 'python manage.py test --noinput <test_module> > /tmp/test-output.txt 2>&1; cat /tmp/test-output.txt | python scripts/filter_failed_tests.py'
    ```
- **Coverage for selective testing**: replace `<test_module>` with the dotted path of the test module and `<path/to/source_file>.py` with the source file you want a coverage report on (e.g. `django_q/cluster.py`). Multiple files can be passed comma-separated:
    ```bash
    docker compose -f test-services-docker-compose.yaml run --remove-orphans --rm integration-tests bash -c 'coverage run manage.py test --noinput <test_module> && coverage combine && coverage report --include=<path/to/source_file>.py'
    ```
- Run the full library suite before declaring a change complete:
    ```bash
    docker compose -f test-services-docker-compose.yaml run --remove-orphans --rm integration-tests
    ```
- **Playwright E2E**: specs live under `playwright/tests/`. The runner uses a two-tier project layout (a parallel tier + a chained-serial tier) defined in `playwright/playwright.config.ts`. Before adding a new spec, read the `PARALLELISM MODEL` comment block at the top of that file — it documents which file-cache keys are global versus per-task and dictates which tier the new spec belongs in. Specs that read/reset `signal-counts` or `chain-progress-log` must be added as a new chained `serial-<name>` project; everything else stays in `parallel`.

## Lint & format

- Run after the implementation is complete (no need to re-run tests after):
    ```bash
    docker compose -f test-services-docker-compose.yaml run --remove-orphans --rm lint-formatter
    ```

## Documentation

- Update `CHANGELOG.md` only when `./django_q/` (the library source) changes, but not including the `tests` folder. Use the active `[X.Y.Z]` heading and `Added` / `Changed` / `Fixed` / `Removed` subsections. Skip it for repo-tooling or sample-project edits.
- Update `README.md` when public API, install steps, or supported Python/Django versions change.
- Review the docs site under `docs/` whenever you change public API, `Q_CLUSTER` settings, brokers, signals, management commands, or schedule types; update the matching `docs/*.md` page using the existing conventions (Material admonitions, reference tables, relative `page.md#anchor` links) and verify with `mkdocs build --strict`.
- Do **not** create new repo-root docs (`*.md`) unless explicitly asked; documentation pages live under `docs/`.

## Commits

- Use Conventional Commits.

## Deployment

- Releases are tag-driven via `.github/workflows/release.yml`. Pushing an annotated tag matching the version number publishes to PyPI.
- Never edit `pyproject.toml`'s `version` by hand — the publish workflow runs `poetry version $TAG_NAME` from the tag.
