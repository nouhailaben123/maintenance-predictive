# Charge .env dans la session PowerShell courante, puis cible localhost (hors Docker).
# Usage : . .\scripts\dev_env.ps1      (le point et l'espace au début sont importants)
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s][^=]*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    Set-Item -Path "env:$($k.Trim())" -Value $v.Trim()
}
$env:RABBITMQ_HOST = "localhost"
$env:POSTGRES_HOST = "localhost"
Write-Host "Variables chargées. RabbitMQ=$env:RABBITMQ_HOST Postgres=$env:POSTGRES_HOST user=$env:RABBITMQ_USER"