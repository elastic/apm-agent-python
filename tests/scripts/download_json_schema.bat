: Adding schema feature download for windows
mkdir .\tests\tempSchema
curl https://codeload.github.com/elastic/apm-server/zip/master -o .\tests\tempSchema\master.zip
7z x .\tests\tempSchema\master.zip -o.\tests\tempSchema *.json -y -r
mkdir .\tests\.schemacache
xcopy .\tests\tempSchema\apm-server-master\docs\spec\* .\tests\.schemacache /Y /S /Q
del .\tests\tempSchema\ /F /Q /S  1>nul
