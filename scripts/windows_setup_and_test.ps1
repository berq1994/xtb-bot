Param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/6] Kontrola slozky projektu..."
if (-not (Test-Path "requirements.txt")) {
    throw "Nenasel jsem requirements.txt. Spust script z rootu repozitare xtb-bot."
}

Write-Host "[2/6] Vytvarim virtualni prostredi (.venv)..."
& $PythonExe -m venv .venv

$VenvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Nepodarilo se najit $VenvPython"
}

Write-Host "[3/6] Aktualizuji pip..."
& $VenvPython -m pip install --upgrade pip

Write-Host "[4/6] Instaluji zavislosti..."
& $VenvPython -m pip install -r requirements.txt

Write-Host "[5/6] Kontrola test package..."
if (-not (Test-Path "tests")) {
    New-Item -ItemType Directory -Path "tests" | Out-Null
}
if (-not (Test-Path "tests\__init__.py")) {
    Set-Content "tests\__init__.py" '"""Test package for unittest discovery."""'
}

Write-Host "[6/6] Spoustim testy..."
& $VenvPython -m unittest discover -s tests -p "test_*.py" -t . -v

Write-Host "Hotovo. Pro dalsi spusteni pouzij:"
Write-Host "  .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p \"test_*.py\" -t . -v"
