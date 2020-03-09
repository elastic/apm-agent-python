: Run the tests in Windows
@echo off
echo "Download json schema dependencies"
call .\tests\scripts\download_json_schema.bat
echo "Download gherkin feature dependencies"
call .\tests\scripts\download_gherkin_features.bat

set PYTEST_JUNIT="--junitxml=.\tests\python-agent-junit.xml"
if "%ASYNCIO%" == "true" call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% -m "not integrationtest"
if "%ASYNCIO%" == "false" call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pytest %PYTEST_JUNIT% --ignore-glob="*/asyncio/*" -m "not integrationtest"
call .\tests\appveyor\build.cmd %PYTHON%\python.exe setup.py bdist_wheel
