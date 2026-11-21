[CmdletBinding()]
param(
    [string]$PythonVersion = "3.15",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$localToolsPath = Join-Path $projectRoot ".tools"
$localUvPath = Join-Path $localToolsPath "uv\uv.exe"

if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "requirements.txt was not found at $requirementsPath"
}

function Get-UvExecutable {
    $installedUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $installedUv) {
        return $installedUv.Source
    }

    if (Test-Path -LiteralPath $localUvPath -PathType Leaf) {
        return $localUvPath
    }

    Write-Host "uv was not found; installing a project-local copy..."
    $installerUrl = "https://astral.sh/uv/install.ps1"
    $installerPath = Join-Path ([System.IO.Path]::GetTempPath()) (
        "install-uv-" + [guid]::NewGuid().ToString("N") + ".ps1"
    )

    try {
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        $env:UV_INSTALL_DIR = Join-Path $localToolsPath "uv"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installerPath
        if ($LASTEXITCODE -ne 0) {
            throw "The uv installer exited with code $LASTEXITCODE"
        }
    }
    finally {
        if (Test-Path -LiteralPath $installerPath) {
            Remove-Item -LiteralPath $installerPath -Force
        }
    }

    if (-not (Test-Path -LiteralPath $localUvPath -PathType Leaf)) {
        throw "uv installation completed without creating $localUvPath"
    }

    return $localUvPath
}

$uv = Get-UvExecutable
$env:UV_PYTHON_INSTALL_DIR = Join-Path $localToolsPath "python"

Push-Location $projectRoot
try {
    Write-Host "Installing Python $PythonVersion if needed..."
    & $uv python install $PythonVersion
    if ($LASTEXITCODE -ne 0) {
        throw "Python installation failed with exit code $LASTEXITCODE"
    }

    if ($Recreate -and (Test-Path -LiteralPath $venvPath)) {
        $resolvedVenv = [System.IO.Path]::GetFullPath($venvPath)
        $expectedVenv = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".venv"))
        if ($resolvedVenv -ne $expectedVenv -or $resolvedVenv -eq $projectRoot) {
            throw "Refusing to remove unexpected virtual environment path: $resolvedVenv"
        }
        Write-Host "Removing the existing virtual environment..."
        Remove-Item -LiteralPath $resolvedVenv -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Write-Host "Creating .venv with Python $PythonVersion..."
        & $uv venv $venvPath --python $PythonVersion
        if ($LASTEXITCODE -ne 0) {
            throw "Virtual environment creation failed with exit code $LASTEXITCODE"
        }
    }

    $actualVersion = (& $venvPython -c "import sys; print('.'.join(map(str, sys.version_info[:2])))").Trim()
    if ($actualVersion -ne $PythonVersion) {
        throw ".venv uses Python $actualVersion, not $PythonVersion. Run .\setup_env.ps1 -Recreate to rebuild it."
    }

    Write-Host "Installing dependencies from requirements.txt..."
    & $uv pip install --python $venvPython --upgrade --requirements $requirementsPath --link-mode copy
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE"
    }

    Write-Host "Verifying imports..."
    & $venvPython -c "import cachetools, defusedxml, fastapi, httpx, pytest, typer, uvicorn; print('Dependency imports OK')"
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency import verification failed with exit code $LASTEXITCODE"
    }

    & $uv pip check --python $venvPython
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency consistency check failed with exit code $LASTEXITCODE"
    }

    Write-Host "Installing the project in editable mode..."
    & $uv pip install --python $venvPython --editable $projectRoot --link-mode copy
    if ($LASTEXITCODE -ne 0) {
        throw "Editable project installation failed with exit code $LASTEXITCODE"
    }

    & $venvPython --version
    & $venvPython -m ruff --version
    & $venvPython -m pytest --version

    Write-Host ""
    Write-Host "Environment setup complete."
    Write-Host "Activate it with: .\.venv\Scripts\Activate.ps1"
    Write-Host "Or run tools directly with: .\.venv\Scripts\python.exe"
}
finally {
    Pop-Location
}
