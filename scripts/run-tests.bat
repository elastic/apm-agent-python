: Run the tests in Windows
: It does require the below list of environment variables:
:  - VERSION: the python version.
:  - ASYNCIO: if asyncio is enabled or not.
:  - PYTHON: the python installation path.
@echo off

@echo on
set VENV_PYTHON=%cd%\venv\Scripts\

set COVERAGE_FILE=.coverage.windows.%VERSION%.%WEBFRAMEWORK%.%ASYNCIO%
set IGNORE_PYTHON3_WITH_PYTHON2=
if "%VERSION%" == "2.7" set IGNORE_PYTHON3_WITH_PYTHON2=--ignore-glob="*\py3_*.py"

set PYTEST_JUNIT="--junitxml=.\tests\windows-%VERSION%-%WEBFRAMEWORK%-%ASYNCIO%-python-agent-junit.xml"
if "%ASYNCIO%" == "true" (
    %VENV_PYTHON%\python.exe -m pytest %PYTEST_JUNIT% %IGNORE_PYTHON3_WITH_PYTHON2% --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest" || cmd /c exit /b 1
)
if "%ASYNCIO%" == "false" (
    %VENV_PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --ignore-glob="*\asyncio*\*" %IGNORE_PYTHON3_WITH_PYTHON2% --cov --cov-context=test --cov-branch --cov-config=setup.cfg -m "not integrationtest" || cmd /c exit /b 1
)
call %VENV_PYTHON%\python.exe setup.py bdist_wheel
