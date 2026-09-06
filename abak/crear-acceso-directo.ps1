<#
    Abak — deja un acceso directo en el Escritorio.
    A partir de ahi, arrancar Abak es un doble clic.
#>

$raiz      = $PSScriptRoot
$destino   = Join-Path $raiz "Iniciar Abak.bat"
$escritorio = [Environment]::GetFolderPath("Desktop")
$atajo     = Join-Path $escritorio "Abak.lnk"

$shell = New-Object -ComObject WScript.Shell

function Atajo($nombre, $bat, $descripcion) {
    $acceso = $shell.CreateShortcut((Join-Path $escritorio $nombre))
    $acceso.TargetPath       = Join-Path $raiz $bat
    $acceso.WorkingDirectory = $raiz
    $acceso.Description      = $descripcion
    $acceso.WindowStyle      = 7   # minimizada: los servidores viven en sus propias ventanas
    $acceso.Save()
}

Atajo "Abak.lnk" "Iniciar Abak.bat" `
      "Abak - analisis economico sin codigo (solo en esta computadora)"

Atajo "Abak en red.lnk" "Iniciar Abak en red.bat" `
      "Abak accesible desde el celular y otros aparatos de tu red"

Write-Host ""
Write-Host "  Listo. Tienes dos accesos en el Escritorio:" -ForegroundColor Green
Write-Host ""
Write-Host "    Abak           solo en esta computadora" -ForegroundColor Green
Write-Host "    Abak en red    tambien desde el celular y la laptop" -ForegroundColor Green
Write-Host ""
Write-Host "  Para el segundo, la primera vez corre tambien:" -ForegroundColor DarkGray
Write-Host "    Permitir Abak en la red.bat   (abre el puerto en el Firewall)" -ForegroundColor DarkGray
Write-Host ""
Read-Host "Enter para cerrar"
