: Adding schema feature download for windows
@echo off
SET TMP_FOLDER=.\tests\tempSchema
SET FOLDER=.\tests\.schemacache
SET APM_SERVER_BRANCH=master

mkdir %TMP_FOLDER%
curl -s https://codeload.github.com/elastic/apm-server/zip/%APM_SERVER_BRANCH% -o %TMP_FOLDER%\%APM_SERVER_BRANCH%.zip
7z x %TMP_FOLDER%\%APM_SERVER_BRANCH%.zip -o%TMP_FOLDER% *.json -y -r
mkdir %FOLDER%
xcopy %TMP_FOLDER%\apm-server-master\docs\spec\* %FOLDER% /Y /S /Q
del %TMP_FOLDER%\ /F /Q /S 1>nul
