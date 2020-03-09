: Required tools before running the tests in windows.

: Install dependencies
: See https://devblogs.microsoft.com/python/unable-to-find-vcvarsall-bat/
choco install windows-sdk-7.1 -y --no-progress -r --version 5.1.0
refreshenv

: We need wheel installed to build wheels
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install -U wheel pip setuptools
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install -r tests\requirements\requirements-%WEBFRAMEWORK%.txt
call .\tests\appveyor\build.cmd %PYTHON%\python.exe -m pip install psutil
