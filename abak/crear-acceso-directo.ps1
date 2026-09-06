<#
    Abak — deja un acceso directo en el Escritorio.
    A partir de ahi, arrancar Abak es un doble clic.
#>

$raiz      = $PSScriptRoot
$destino   = Join-Path $raiz "Iniciar Abak.bat"
$escritorio = [Environment]::GetFolderPath("Desktop")
$atajo     = Join-Path $escritorio "Abak.lnk"

$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($atajo)
$acceso.TargetPath       = $destino
$acceso.WorkingDirectory = $raiz
$acceso.Description      = "Abak - analisis economico sin codigo"
$acceso.WindowStyle      = 7   # minimizada: los servidores viven en sus propias ventanas
$acceso.Save()

Write-Host ""
Write-Host "  Listo. Tienes 'Abak' en el Escritorio." -ForegroundColor Green
Write-Host "  Doble clic y se abre solo en el navegador." -ForegroundColor Green
Write-Host ""
Read-Host "Enter para cerrar"
