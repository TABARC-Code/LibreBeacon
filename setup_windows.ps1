# The batch installer also works if PowerShell script execution is disabled.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& (Join-Path $PSScriptRoot 'INSTALL-WINDOWS.bat')
if ($LASTEXITCODE -ne 0) { throw 'Installation failed; see the message above.' }
