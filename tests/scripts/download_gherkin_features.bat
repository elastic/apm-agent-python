mkdir .\tests\tempFeatures
curl https://codeload.github.com/elastic/apm/zip/master -o .\tests\tempFeatures\features.zip
7z x .\tests\tempFeatures\features.zip -o.\tests\tempFeatures *.feature -y -r
mkdir .\tests\bdd\features
xcopy .\tests\tempFeatures\apm-master\tests\agents\gherkin-specs\* .\tests\bdd\features /Y /S
del .\tests\tempFeatures\ /F /Q /S