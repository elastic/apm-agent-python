: Required tools before running the tests in windows.
: It does require the below list of environment variables:
:  - DISTUTILS_USE_SDK: optional
:  - PYTHON: the python installation path.
:  - WEBFRAMEWORK: the framework to be installed.
@echo off

IF "%DISTUTILS_USE_SDK%"=="1" (
    : See https://devblogs.microsoft.com/python/unable-to-find-vcvarsall-bat/
    ECHO Install dependencies
    choco install windows-sdk-7.1 -y --no-progress -r
    call "C:\Program Files\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" /x64
) ELSE (
    ECHO Setup local installation
    : See https://stackoverflow.com/a/43570522
    call "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\Common7\Tools\vsdevcmd.bat" -arch=amd64
)

: We need wheel installed to build wheels
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install -U wheel pip setuptools
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install -r tests\requirements\requirements-%WEBFRAMEWORK%.txt
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install psutil
