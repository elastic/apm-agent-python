SETLOCAL EnableDelayedExpansion
set pythonVersion=%1
set pythonExecutable=%2
set majorVersion=!pythonVersion:~0,1!
set minorVersion=!pythonVersion:~2,1!
if %majorVersion% EQU 3 (choco install python3 --version=%1 -y --force --allow-downgrade) else (choco install python2 -y --force)
if %majorVersion% EQU 3 ( if %minorVersion% NEQ 7 (move c:\%pythonExecutable%\python.exe c:\%pythonExecutable%\%pythonExecutable%.exe)) else (move c:\%pythonExecutable%\python.exe c:\%pythonExecutable%\%pythonExecutable%.exe)
SETLOCAL DisableDelayedExpansion

