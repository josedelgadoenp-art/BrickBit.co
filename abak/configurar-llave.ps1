<#
    Abak — guarda la llave de la API de Anthropic.

    Existe porque un instructivo con un hueco que rellenar es una trampa: dos
    veces seguidas se guardo el texto de ejemplo («sk-ant-tu-llave»,
    «<pega aqui la llave completa>») en lugar de la llave. No es descuido de
    quien lo pega: es que la linea se ve completa y se copia entera.

    Aqui no hay nada que sustituir. Se pide la llave, se revisa antes de
    guardarla, y se dice que sigue.
#>

$ErrorActionPreference = "Stop"

function Escribir($t, $c = "Gray") { Write-Host $t -ForegroundColor $c }

Escribir ""
Escribir "  Llave de la API de Anthropic" "Green"
Escribir ""
Escribir "  Se crea en console.anthropic.com, en la seccion API Keys." "DarkGray"
Escribir "  Empieza con sk-ant- y pasa de 100 caracteres." "DarkGray"
Escribir "  Ojo: NO es la contrasena de claude.ai, y el uso por API se paga aparte" "DarkGray"
Escribir "  de la suscripcion." "DarkGray"
Escribir ""

$llave = (Read-Host "  Pega la llave y presiona Enter").Trim()

if ([string]::IsNullOrWhiteSpace($llave)) {
    Escribir ""
    Escribir "  No pegaste nada. No se guardo nada." "Yellow"
    Escribir ""
    Read-Host "  Enter para cerrar"; exit 1
}
if (-not $llave.StartsWith("sk-ant-")) {
    Escribir ""
    Escribir "  Eso no parece una llave de la API: las llaves empiezan con sk-ant-." "Yellow"
    Escribir "  No se guardo nada." "Yellow"
    Escribir ""
    Read-Host "  Enter para cerrar"; exit 1
}
if ($llave.Length -lt 50) {
    Escribir ""
    Escribir "  Pegaste $($llave.Length) caracteres y una llave pasa de 100." "Yellow"
    Escribir "  Parece que se copio incompleta, o que es el texto de un ejemplo." "Yellow"
    Escribir "  No se guardo nada." "Yellow"
    Escribir ""
    Read-Host "  Enter para cerrar"; exit 1
}

setx ANTHROPIC_API_KEY $llave | Out-Null
# `setx` escribe en el registro, no en esta sesion: sin esto, la ventana desde
# la que se lanza Abak enseguida seguiria sin ver la llave.
$env:ANTHROPIC_API_KEY = $llave

Escribir ""
Escribir "  Guardada: $($llave.Length) caracteres, empieza con $($llave.Substring(0,11))..." "Green"
Escribir ""
Escribir "  Ahora CIERRA las ventanas de PowerShell que tengas abiertas y vuelve a" "Gray"
Escribir "  abrir Abak. Las ventanas viejas no ven la llave nueva." "Gray"
Escribir ""
Read-Host "  Enter para cerrar"
