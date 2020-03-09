: Run the tests in Windows
call .\tests\scripts\download_json_schema.bat
call .\tests\scripts\download_gherkin_features.bat
if "%ASYNCIO%" == "true" call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pytest -m "not integrationtest"
if "%ASYNCIO%" == "false" call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pytest --ignore-glob="*/asyncio/*" -m "not integrationtest"
call .\tests\appveyor\build.cmd %PYTHON%\python.exe setup.py bdist_wheel
