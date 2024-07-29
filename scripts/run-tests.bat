: Run the tests in Windows
: It does require the below list of environment variables:
:  - VERSION: the python version.
:  - ASYNCIO: if asyncio is enabled or not.
:  - PYTHON: the python installation path.
@echo off

@echo on
set VENV_PYTHON=%cd%\venv\Scripts\

set COVERAGE_FILE=.coverage.windows.%VERSION%.%FRAMEWORK%.%ASYNCIO%

set PYTEST_JUNIT="--junitxml=.\tests\windows-%VERSION%-%FRAMEWORK%-%ASYNCIO%-python-agent-junit.xml"
if "%ASYNCIO%" == "true" (
    %VENV_PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest" || exit /b 1
)
if "%ASYNCIO%" == "false" (
    %VENV_PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --ignore-glob="*\asyncio*\*" --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest" || exit /b 1
)
call %VENV_PYTHON%\python.exe setup.py bdist_wheel
