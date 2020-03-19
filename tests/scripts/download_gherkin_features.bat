: Adding gherkin feature download for windows
@echo off
SET TMP_FOLDER=.\tests\tempFeatures
SET FOLDER=.\tests\bdd\features
SET APM_BRANCH=master

mkdir %TMP_FOLDER%
curl -s https://codeload.github.com/elastic/apm/zip/%APM_BRANCH% -o %TMP_FOLDER%\features.zip
7z x %TMP_FOLDER%\features.zip -o%TMP_FOLDER% *.feature -y -r
mkdir %FOLDER%
xcopy %TMP_FOLDER%\apm-master\tests\agents\gherkin-specs\* %FOLDER% /Y /S /Q
del %TMP_FOLDER%\ /F /Q /S 1>nul
