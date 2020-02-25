SETLOCAL EnableDelayedExpansion
choco uninstall python3 -y
set pythonVersion=%1
set pythonVersion=!pythonVersion:~0,1!
echo !pythonVersion!
if %pythonVersion% EQU 3 (choco install python3 --version=%1 -y --force) else (choco install python2 -y --force)
SETLOCAL DisableDelayedExpansion

