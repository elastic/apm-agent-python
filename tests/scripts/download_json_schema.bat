mkdir .\tests\tempSchema
curl https://codeload.github.com/elastic/apm-server/zip/master -o .\tests\tempSchema\master.zip
7z x .\tests\tempSchema\master.zip -o.\tests\tempSchema *.json -y -r
mkdir .\tests\.schemacache
copy .\tests\tempSchema\apm-server-master\docs\spec\* .\tests\.schemacache
del .\tests\tempSchema\ /F /Q /S