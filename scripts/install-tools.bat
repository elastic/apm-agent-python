: Required tools before running the tests in windows.
: It does require the below list of environment variables:
:  - PYTHON: the python installation path.
:  - WEBFRAMEWORK: the framework to be installed.
@echo off

: Prepare the env context
call "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\Common7\Tools\vsdevcmd.bat" -arch=amd64

: We need wheel installed to build wheels
call %PYTHON%\python.exe -m pip install -U wheel pip setuptools
call %PYTHON%\python.exe -m pip install -r tests\requirements\reqs-%WEBFRAMEWORK%.txt
call %PYTHON%\python.exe -m pip install psutil
