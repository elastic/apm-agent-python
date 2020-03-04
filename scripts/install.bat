: Required tools before running the tests in windows.

: Needed to compile pymongo
if "%platform%" == "x86" call "%VS120COMNTOOLS%\..\..\VC\vcvarsall.bat"
if "%platform%" == "x64" "C:\Program Files\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" /x64
if "%platform%" == "x64" call "%VS120COMNTOOLS%\..\..\VC\vcvarsall.bat" x86_amd64
: We need wheel installed to build wheels
".\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe -m pip install -U wheel pip setuptools"
".\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe -m pip install -r tests\\requirements\\requirements-%WEBFRAMEWORK%.txt"
".\\tests\\appveyor\\build.cmd %PYTHON%\\python.exe -m pip install psutil"
