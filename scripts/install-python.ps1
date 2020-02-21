# Abort with non zero exit code on errors
$ErrorActionPreference = "Stop"

Write-Host("Getting latest Python3 version for {0} ..." -f $env:VERSION)
& choco list python3 --exact --by-id-only --all | Select-String -Pattern "python3 $env:VERSION"
$Version = $(choco list python3 --exact --by-id-only --all) | Select-String -Pattern "python3 $env:VERSION" | %{$_.ToString().split(" ")[1]} | sort | Select-Object -Last 1

Write-Host("Installing Python3 {0} ..." -f $Version)
& choco install python3 --no-progress -y --version "$Version"
