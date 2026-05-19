#!/usr/bin/env bash

# https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin
# -e  Exit immediately if a command exits with a non-zero status.
# -x  Print commands and their arguments as they are executed.
set -e

REPORTS_FOLDER_PATH=tests-reports

# Run the following: docker compose run --rm integration-tests bash
# Then you can explore the options by issuing: coverage run manage.py test --help
coverage run manage.py test --verbosity 2 --durations 10 --timing --testrunner=xmlrunner.extra.djangotestrunner.XMLTestRunner
# `combine` is a no-op when not running with --parallel but harmless and keeps the
# downstream `coverage report/html/xml` invocations identical to the parallel layout.
coverage combine || true
coverage report -m
coverage html -d $REPORTS_FOLDER_PATH/html
coverage xml -o $REPORTS_FOLDER_PATH/coverage.xml
