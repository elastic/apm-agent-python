SETLOCAL EnableDelayedExpansion
set pythonVersion=%1
set pythonExecutable=%2
set majorVersion=!pythonVersion:~0,1!
set minorVersion=!pythonVersion:~2,1!
if %majorVersion% EQU 2 (set pyArgs=--ignore-glob="*/py3_*.py" --ignore-glob="*/asyncio/*") else ( if %minorVersion% EQU 5 (set pyArgs=--ignore-glob="*/asyncio/*"))
%pythonExecutable% -m pytest --cov --cov-report xml:coverage.xml %pyArgs%
SETLOCAL DisableDelayedExpansion