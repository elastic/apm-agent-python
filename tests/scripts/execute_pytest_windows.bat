SETLOCAL EnableDelayedExpansion
set pythonVersion=%1
set majorVersion=!pythonVersion:~0,1!
echo !majorVersion!
set minorVersion=!pythonVersion:~2,1!
echo !minorVersion!
if %majorVersion% EQU 2 (set pyArgs="--ignore-glob='*/py3_*.py' --ignore-glob='*/asyncio/*'") else ( if %minorVersion% EQU 5 (set pyArgs="--ignore-glob='*/asyncio/*'"))
%2 -m pytest --vv --cov --cov-report xml:coverage.xml %pyArgs%
SETLOCAL DisableDelayedExpansion