.\tests\scripts\install_chocolatey.bat^
    && refreshenv^
    && .\tests\scripts\install_python.bat %1 %2^
    && refreshenv^
    && dir c:\
    && %2 -m pip install -r .\tests\requirements\requirements-base.txt^
    && .\tests\scripts\download_json_schema.bat^
    && .\tests\scripts\download_gherkin_features.bat^
    && .\tests\scripts\execute_pytest_windows.bat %1 %2