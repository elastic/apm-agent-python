: Run the tests in Windows
: It does require the below list of environment variables:
:  - ASYNCIO: if asyncio is enabled or not.
:  - PYTHON: the python installation path.
@echo off

ECHO Download json schema dependencies
call .\tests\scripts\download_json_schema.bat
ECHO Download gherkin feature dependencies
call .\tests\scripts\download_gherkin_features.bat

set PYTEST_JUNIT="--junitxml=.\tests\python-agent-junit.xml"
if "%ASYNCIO%" == "true" call %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% -m "not integrationtest"
if "%ASYNCIO%" == "false" call %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --ignore-glob="*/asyncio/*" -m "not integrationtest"
call %PYTHON%\python.exe setup.py bdist_wheel
