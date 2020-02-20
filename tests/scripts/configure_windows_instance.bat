call .\tests\scripts\install_chocolatey.bat
call .\tests\scripts\install_python.bat %1
call .\tests\scripts\install_modules.bat %2
call .\tests\scripts\download_json_schema.bat
python -m pytest