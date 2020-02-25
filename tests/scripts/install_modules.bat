SETLOCAL EnableDelayedExpansion
set pythonVersion=%1
set pythonExecutable=%2
set majorVersion=!pythonVersion:~0,1!
echo !majorVersion!
if %majorVersion% EQU 2 (!pythonExecutable! -m pip install -r .\tests\requirements\requirements-base.txt) else (!pythonExecutable! -m pip install /r .\tests\requirements\requirements-base.txt)
SETLOCAL DisableDelayedExpansion