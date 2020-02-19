mkdir ./tests/tempSchema
curl https://codeload.github.com/elastic/apm-server/zip/master -OutFile ./tests/tempSchema/master.zip
expand-archive -Path ./tests/tempSchema/master.zip -DestinationPath ./tests/tempSchema
mkdir ./tests/.schemacache
mv -Force ./tests/tempSchema/apm-server-master/docs/spec/* ./tests/.schemacache
del ./tests/tempSchema/ -Confirm:$false -Recurse -Force