$ErrorActionPreference = "Stop"
$Zip = "https://github.com/Cillian-Cooke/hexshift/archive/refs/heads/main.zip"
$Dest = Join-Path $env:LOCALAPPDATA "hexshift"

$Exe = $null
$PyArgs = @()
foreach ($name in @("py", "python", "python3")) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $found) { continue }
    try {
        if ($name -eq "py") {
            $ver = & $found.Source -3 -c "import sys; print('%d.%d' % (sys.version_info.major, sys.version_info.minor))"
            $candidateExe = $found.Source
            $candidateArgs = @("-3")
        } else {
            $ver = & $found.Source -c "import sys; print('%d.%d' % (sys.version_info.major, sys.version_info.minor))"
            $candidateExe = $found.Source
            $candidateArgs = @()
        }
        $parts = $ver.Split(".")
        if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10)) {
            $Exe = $candidateExe
            $PyArgs = $candidateArgs
            break
        }
    } catch {
        continue
    }
}

if (-not $Exe) {
    Write-Error "Hexshift needs Python 3.10+. Install it from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
}

Write-Host "Installing Hexshift into $Dest ..."
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
& $Exe @PyArgs -m venv (Join-Path $Dest "venv")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$VenvPy = Join-Path $Dest "venv\Scripts\python.exe"
& $VenvPy -m pip install --upgrade pip | Out-Null
& $VenvPy -m pip install --upgrade $Zip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Hexshift is installed. Launching..."
Write-Host "Later you can run:  $VenvPy -m hexshift"
& $VenvPy -m hexshift @args
exit $LASTEXITCODE
