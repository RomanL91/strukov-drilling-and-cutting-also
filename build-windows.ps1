<#
.SYNOPSIS
    Сборка приложения под Windows — замена `make pack-windows` там, где make нет.

.DESCRIPTION
    Метаданные (имя, продукт, компания, копирайт) берутся из pyproject.toml,
    версия — из `poetry version`, поэтому в скрипте их дублировать не нужно.

    Два режима:
      pack   — один .exe через PyInstaller, Visual Studio не нужна (по умолчанию);
      native — бандл Flutter, стартует быстрее, но требует C++-тулчейн VS.

.PARAMETER Mode
    Способ сборки: pack или native.

.PARAMETER Clean
    Удалить каталоги build и dist перед сборкой.

.PARAMETER DryRun
    Показать команду сборки и выйти, ничего не запуская.

.EXAMPLE
    .\build-windows.ps1
    Собирает dist\StrukovDrilling.exe.

.EXAMPLE
    .\build-windows.ps1 -Mode native -Clean
    Чистая сборка нативным бандлом Flutter.
#>

[CmdletBinding()]
param(
    [ValidateSet("pack", "native")]
    [string]$Mode = "pack",
    [switch]$Clean,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Без этого кириллица в метаданных exe и в выводе сборщика превращается в вопросы.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Assert-ExitCode {
    <#
    .SYNOPSIS
        Прерывает скрипт, если последняя внешняя команда завершилась ошибкой.
    #>
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step — код возврата $LASTEXITCODE"
    }
}

function Get-BuildMetadata {
    <#
    .SYNOPSIS
        Читает метаданные сборки из pyproject.toml.
    #>
    $reader = @'
import json
import pathlib
import tomllib

data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
flet = data.get("tool", {}).get("flet", {})
poetry = data.get("tool", {}).get("poetry", {})
print(json.dumps({
    "artifact": flet.get("artifact", "app"),
    "product": flet.get("product", ""),
    "company": flet.get("company", ""),
    "copyright": flet.get("copyright", ""),
    "description": poetry.get("description", ""),
}, ensure_ascii=False))
'@

    $json = $reader | poetry run python -
    Assert-ExitCode "Чтение pyproject.toml"
    return $json | ConvertFrom-Json
}

if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    throw "Poetry не найден в PATH. Установка: pipx install poetry"
}

$version = (poetry version -s).Trim()
Assert-ExitCode "Чтение версии проекта"
$meta = Get-BuildMetadata

Write-Host ""
Write-Host "Сборка $($meta.artifact) $version | режим: $Mode" -ForegroundColor Cyan
Write-Host ""

if ($Clean) {
    foreach ($path in @("build", "dist")) {
        if (Test-Path $path) {
            Write-Host "Удаляю $path"
            Remove-Item $path -Recurse -Force
        }
    }
}

if ($Mode -eq "pack") {
    # PyInstaller лежит в группе dev — если его нет, ставим зависимости.
    poetry run python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PyInstaller не установлен, выполняю poetry install" -ForegroundColor Yellow
        poetry install --no-interaction
        Assert-ExitCode "Установка зависимостей"
    }

    $arguments = @(
        "run", "flet", "pack", "main.py",
        "--name", $meta.artifact,
        "--product-name", $meta.product,
        "--file-description", $meta.description,
        "--company-name", $meta.company,
        "--copyright", $meta.copyright,
        "--product-version", $version,
        "--file-version", "$version.0",
        "--yes"
    )
    $output = Join-Path "dist" "$($meta.artifact).exe"
}
else {
    # Метаданные native-сборка берёт из [tool.flet] сама.
    $arguments = @("run", "flet", "build", "windows", "--build-version", $version, "--yes")
    $output = Join-Path "build\windows" "$($meta.artifact).exe"
}

Write-Host "poetry $($arguments -join ' ')" -ForegroundColor DarkGray
Write-Host ""

if ($DryRun) {
    Write-Host "Пробный запуск: команда не выполнялась." -ForegroundColor Yellow
    return
}

$started = Get-Date
& poetry @arguments
if ($LASTEXITCODE -ne 0) {
    if ($Mode -eq "native") {
        Write-Host ""
        Write-Host "Нативная сборка требует C++-тулчейн Visual Studio:" -ForegroundColor Yellow
        Write-Host '  winget install --id Microsoft.VisualStudio.2022.BuildTools --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"'
        Write-Host "Без него используйте режим pack (по умолчанию)." -ForegroundColor Yellow
    }
    throw "Сборка не удалась — код возврата $LASTEXITCODE"
}

$elapsed = (Get-Date) - $started
Write-Host ""

if (Test-Path $output) {
    $size = [math]::Round((Get-Item $output).Length / 1MB, 1)
    Write-Host "Готово за $([int]$elapsed.TotalSeconds) с: $((Resolve-Path $output).Path) ($size МБ)" -ForegroundColor Green
}
else {
    # Flet меняет раскладку каталогов от версии к версии — не гадаем, а показываем найденное.
    Write-Host "Сборка завершена за $([int]$elapsed.TotalSeconds) с, но $output не найден." -ForegroundColor Yellow
    Get-ChildItem -Path "build", "dist" -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host "  найдено: $($_.FullName)" }
}
