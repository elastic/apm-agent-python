call .\tests\scripts\install_chocolatey.bat
call refreshenv
call .\tests\scripts\install_python.bat %1
call refreshenv
call .\tests\scripts\install_modules.bat
call .\tests\scripts\download_json_schema.bat
call .\tests\scripts\download_gherkin_features.bat
call py -m pytest