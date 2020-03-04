: Run the tests in Windows
bash .\\tests\\scripts\\download_json_schema.sh
bash .\\tests\\scripts\\download_gherkin_features.sh
if "%ASYNCIO%" == "true" call appveyor-retry .\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe -m pytest -m "not integrationtest"
if "%ASYNCIO%" == "false" call appveyor-retry .\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe -m pytest --ignore-glob="*/asyncio/*" -m "not integrationtest"
".\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe setup.py bdist_wheel"
