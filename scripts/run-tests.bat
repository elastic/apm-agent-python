: Run the tests in Windows
: It does require the below list of environment variables:
:  - VERSION: the python version.
:  - ASYNCIO: if asyncio is enabled or not.
:  - PYTHON: the python installation path.
@echo off

ECHO Download json schema dependencies
call .\tests\scripts\download_json_schema.bat

@echo on
set COVERAGE_FILE=.coverage.%VERSION%.%WEBFRAMEWORK%
set IGNORE_PYTHON3_WITH_PYTHON2=
if "%VERSION%" == "2.7" set IGNORE_PYTHON3_WITH_PYTHON2=--ignore-glob="*\py3_*.py"

set PYTEST_JUNIT="--junitxml=.\tests\python-agent-junit.xml"
if "%ASYNCIO%" == "true" (
    call %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% %IGNORE_PYTHON3_WITH_PYTHON2% --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest"
)
if "%ASYNCIO%" == "false" (
    call %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --ignore-glob="*\asyncio\*" %IGNORE_PYTHON3_WITH_PYTHON2% --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest"
)
call %PYTHON%\python.exe setup.py bdist_wheel
