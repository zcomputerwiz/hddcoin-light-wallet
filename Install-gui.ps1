$ErrorActionPreference = "Stop"

if ($null -eq (Get-ChildItem env:VIRTUAL_ENV -ErrorAction SilentlyContinue))
{
    Write-Output "This script requires that the HDDcoin Python virtual environment is activated."
    Write-Output "Execute '.\venv\Scripts\Activate.ps1' before running."
    Exit 1
}

if ($null -eq (Get-Command node -ErrorAction SilentlyContinue))
{
    Write-Output "Unable to find Node.js"
    Exit 1
}

Write-Output "Running 'git submodule update --init --recursive'."
Write-Output ""
git submodule update --init --recursive

Set-Location hddcoin-blockchain-gui

$ErrorActionPreference = "SilentlyContinue"
npm install --loglevel=error
npm run audit:fix
npm run build
py ..\installhelper.py

Write-Output ""
Write-Output "HDDcoin blockchain Install-gui.ps1 completed."
Write-Output ""
Write-Output "Type 'cd hddcoin-blockchain-gui' and then 'npm run electron' to start the GUI."
