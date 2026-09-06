<#
    Abak — abre el puerto 3000 en el Firewall de Windows, sólo para redes
    privadas (tu casa), nunca para las públicas.

    Necesita permisos de administrador: click derecho > "Ejecutar con
    PowerShell" no basta. Usa "Permitir Abak en la red.bat", que ya pide la
    elevación.

    Se abre UN puerto, el 3000. El API (8000) se queda escuchando sólo en esta
    máquina: la interfaz le habla desde aquí mismo, así que no hace falta
    exponerlo, y lo que no se expone no se ataca.
#>

$ErrorActionPreference = "Stop"
$regla = "Abak (interfaz local)"

$admin = ([Security.Principal.WindowsPrincipal] `
          [Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
    Write-Host ""
    Write-Host "  Esto necesita permisos de administrador." -ForegroundColor Yellow
    Write-Host "  Usa 'Permitir Abak en la red.bat', que los pide solo." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Enter para cerrar"
    exit 1
}

$existe = Get-NetFirewallRule -DisplayName $regla -ErrorAction SilentlyContinue
if ($existe) {
    Write-Host ""
    Write-Host "  El permiso ya estaba puesto." -ForegroundColor DarkGray
} else {
    New-NetFirewallRule -DisplayName $regla `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000 `
        -Profile Private `
        -Description "Deja entrar a Abak desde otros aparatos de tu red privada." | Out-Null
    Write-Host ""
    Write-Host "  Listo: el puerto 3000 queda abierto en redes PRIVADAS." -ForegroundColor Green
}

Write-Host "  En redes publicas sigue cerrado, a proposito." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Para quitarlo:  Remove-NetFirewallRule -DisplayName '$regla'" -ForegroundColor DarkGray
Write-Host ""
Read-Host "Enter para cerrar"
