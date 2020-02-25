call .\tests\scripts\install_chocolatey.bat
call refreshenv
call .\tests\scripts\install_python.bat %1
call move c:\%2\python.exe c:\%2\%2.exe
call refreshenv
call %2 -m pip install -r .\tests\requirements\requirements-base.txt
call .\tests\scripts\download_json_schema.bat
call .\tests\scripts\download_gherkin_features.bat
call .\tests\scripts\execute_pytest_windows.bat