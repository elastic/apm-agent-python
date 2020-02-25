SETLOCAL EnableDelayedExpansion
set pythonVersion=%1
set pythonVersion=!pythonVersion:~0,1!
echo !pythonVersion!
if %pythonVersion% EQU 3 (choco install python3 --version=%1 -y --force --allow-downgrade) else (choco install python2 -y --force)
move c:\%2\python.exe c:\%2\%2.exe
SETLOCAL DisableDelayedExpansion

