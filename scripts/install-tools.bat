: Required tools before running the tests in windows.
: It does require the below list of environment variables:
:  - PYTHON: the python installation path.
:  - WEBFRAMEWORK: the framework to be installed.
@echo on

: We need wheel installed to build wheels

if [%JENKINS_HOME%] == [] (
set PYTHON_EXECUTABLE=%PYTHON%\python.exe
) else (
set PYTHON_EXECUTABLE=python
)

call %PYTHON_EXECUTABLE% -m venv "%cd%\venv"

call python -m venv "%cd%\venv"
set VENV_PYTHON=%cd%\venv\Scripts\
call %VENV_PYTHON%\python.exe -m pip install -U wheel pip setuptools
call %VENV_PYTHON%\python.exe -m pip install -r tests\requirements\reqs-%WEBFRAMEWORK%.txt
call %VENV_PYTHON%\python.exe -m pip install psutil
