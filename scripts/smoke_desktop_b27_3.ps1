param(
    [string]$TargetRoot = $(Join-Path (Split-Path -Parent $PSScriptRoot) 'local_ui_bugbash')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$TargetRoot = [System.IO.Path]::GetFullPath($TargetRoot)
$null = New-Item -ItemType Directory -Force -Path $TargetRoot

$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ProjectPath = Join-Path $TargetRoot ("desktop_ui_bugbash_project_{0}.json" -f $Timestamp)
$ImportPath = Join-Path $TargetRoot 'import_smoke.txt'
$LogPath = Join-Path $TargetRoot 'desktop_ui_bugbash_setup.log'
$LatestProjectPathFile = Join-Path $TargetRoot 'latest_project_path.txt'
$script:CurrentStep = 'bootstrap'

Remove-Item "$ProjectPath.tmp" -Force -ErrorAction SilentlyContinue
if (Test-Path $ProjectPath) {
    Remove-Item $ProjectPath -Force -ErrorAction SilentlyContinue
}

if (Test-Path (Join-Path $RepoRoot '.venv\Scripts\Activate.ps1')) {
    . (Join-Path $RepoRoot '.venv\Scripts\Activate.ps1')
} elseif (Test-Path (Join-Path $RepoRoot 'venv\Scripts\Activate.ps1')) {
    . (Join-Path $RepoRoot 'venv\Scripts\Activate.ps1')
}

"Desktop UI Bug Bash smoke setup" | Out-File -FilePath $LogPath -Encoding utf8
"RepoRoot=$RepoRoot" | Out-File -FilePath $LogPath -Append -Encoding utf8
"TargetRoot=$TargetRoot" | Out-File -FilePath $LogPath -Append -Encoding utf8
"ProjectPath=$ProjectPath" | Out-File -FilePath $LogPath -Append -Encoding utf8
"LatestProjectPathFile=$LatestProjectPathFile" | Out-File -FilePath $LogPath -Append -Encoding utf8

function Write-Logged {
    param([string]$Message)
    $Message | Tee-Object -FilePath $LogPath -Append
}

function Run-Command {
    param(
        [string]$Name,
        [string[]]$Args
    )
    $script:CurrentStep = $Name
    Write-Logged ""
    Write-Logged (">>> {0}" -f $Name)
    Write-Logged ("CMD> python {0}" -f ($Args -join ' '))

    $output = & python @Args 2>&1
    $exitCode = $LASTEXITCODE

    if ($null -ne $output) {
        foreach ($line in @($output)) {
            Write-Logged ([string]$line)
        }
    }

    Write-Logged ("ExitCode={0}" -f $exitCode)

    if ($exitCode -ne 0) {
        throw "Step failed: $Name exit=$exitCode"
    }
}

function Run-Step {
    param(
        [string]$Name,
        [string[]]$Args
    )
    $AllArgs = @('-m', 'narrative_architect') + $Args
    Run-Command -Name $Name -Args $AllArgs
}

function Run-ProjectStep {
    param(
        [string]$Name,
        [string[]]$Args
    )
    $AllArgs = @('--project', $ProjectPath) + $Args
    Run-Step -Name $Name -Args $AllArgs
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Message
    )
    if (!(Test-Path $Path)) {
        throw $Message
    }
}

function Load-Project {
    Assert-PathExists -Path $ProjectPath -Message "Project file not created: $ProjectPath"
    return Get-Content $ProjectPath -Raw | ConvertFrom-Json
}

function Get-EntityIdByName {
    param([string]$Name)
    $project = Load-Project
    $entity = @($project.entities | Where-Object { $_.name -eq $Name }) | Select-Object -First 1
    if ($null -eq $entity -or [string]::IsNullOrWhiteSpace($entity.id)) {
        throw "Entity id not found for: $Name"
    }
    return [string]$entity.id
}

function Get-FirstId {
    param(
        [string]$CollectionName,
        [string]$Label
    )
    $project = Load-Project
    $items = $project.$CollectionName
    if ($null -eq $items -or @($items).Count -eq 0) {
        throw "$Label not found in project JSON"
    }
    $id = [string](@($items)[0].id)
    if ([string]::IsNullOrWhiteSpace($id)) {
        throw "$Label id empty"
    }
    return $id
}

try {
    Run-Command -Name 'python version' -Args @('--version')
    Run-Command -Name 'python executable' -Args @('-c', 'import sys; print(sys.executable)')
    Run-Command -Name 'install desktop smoke deps' -Args @('-m', 'pip', 'install', '-e', '.', 'pytest', 'PySide6')
    Run-Command -Name 'compileall DesktopHostPySide' -Args @('-m', 'compileall', 'hosts/DesktopHostPySide')
    Run-Command -Name 'pytest architecture' -Args @('-m', 'pytest', 'tests/architecture/', '-q')

    Run-Step -Name 'project create' -Args @('project', 'create', 'Desktop UI Bug Bash', '--path', $ProjectPath)
    Assert-PathExists -Path $ProjectPath -Message "Project file not created after project create: $ProjectPath"
    Set-Content -Path $LatestProjectPathFile -Value $ProjectPath -Encoding utf8

    Run-ProjectStep -Name 'entity create Aria' -Args @('entity', 'create', 'Aria', '--type', 'personaje', '--brief', 'Heroina del smoke')
    Run-ProjectStep -Name 'entity create Torre Negra' -Args @('entity', 'create', 'Torre Negra', '--type', 'localizacion', '--brief', 'Fortaleza del smoke')
    Run-ProjectStep -Name 'entity create Orden del Eclipse' -Args @('entity', 'create', 'Orden del Eclipse', '--type', 'faccion', '--brief', 'Faccion del smoke')
    Run-ProjectStep -Name 'entity create Llave Solar' -Args @('entity', 'create', 'Llave Solar', '--type', 'objeto', '--brief', 'Objeto del smoke')

    $AriaId = Get-EntityIdByName -Name 'Aria'
    $LocationId = Get-EntityIdByName -Name 'Torre Negra'
    $FactionEntityId = Get-EntityIdByName -Name 'Orden del Eclipse'

    Run-ProjectStep -Name 'relation create' -Args @('relation', 'create', $AriaId, $LocationId, '--type', 'esta_ubicado_en', '--desc', 'Aria llega a la Torre Negra')
    Run-ProjectStep -Name 'candidate create' -Args @('candidate', 'create', 'Candidato humo', '--type', 'ENTIDAD', '--data', '{"name":"Eco","entity_type":"personaje"}')
    Run-ProjectStep -Name 'campaign create' -Args @('campaign', 'create', 'Campana Humo', '--world', 'Niebla', '--system', 'DnD', '--tone', 'oscuro', '--genre', 'fantasy', '--description', 'smoke')

    $CampaignId = Get-FirstId -CollectionName 'campaigns' -Label 'Campaign'
    Run-ProjectStep -Name 'campaign player-add' -Args @('campaign', 'player-add', $CampaignId, 'Lucia')
    Run-ProjectStep -Name 'campaign clock-create' -Args @('campaign', 'clock-create', $CampaignId, 'Amenaza', '--max', '4', '--description', 'Clock smoke')

    Run-ProjectStep -Name 'secret create' -Args @('secret', 'create', 'El eclipse oculta una puerta', '--entity', $AriaId)
    $SecretId = Get-FirstId -CollectionName 'secrets' -Label 'Secret'

    Run-ProjectStep -Name 'clue create' -Args @('clue', 'create', 'Un mapa roto apunta a la puerta', '--secret', $SecretId, '--entity', $AriaId)
    Run-ProjectStep -Name 'faction create' -Args @('faction', 'create', 'Orden del Eclipse', '--entity', $FactionEntityId, '--ideology', 'Control', '--methods', 'Intriga')
    Run-ProjectStep -Name 'session create' -Args @('session', 'create', 'Sesion 1', '--campaign', $CampaignId)

    $SessionId = Get-FirstId -CollectionName 'sessions' -Label 'Session'
    $ClueId = Get-FirstId -CollectionName 'clues' -Label 'Clue'
    $FactionId = Get-FirstId -CollectionName 'factions' -Label 'Faction'
    $ClockId = Get-FirstId -CollectionName 'campaign_clocks' -Label 'Campaign clock'

    Run-ProjectStep -Name 'session scene add' -Args @('session', 'scene', 'add', $SessionId, 'Escena 1', '--type', 'prevista', '--target', 'planned')
    Run-ProjectStep -Name 'session link entity location' -Args @('session', 'link', 'entity', $SessionId, $LocationId, '--role', 'location')
    Run-ProjectStep -Name 'session link entity npc' -Args @('session', 'link', 'entity', $SessionId, $AriaId, '--role', 'npc')
    Run-ProjectStep -Name 'session link secret' -Args @('session', 'link', 'secret', $SessionId, $SecretId)
    Run-ProjectStep -Name 'session link clue' -Args @('session', 'link', 'clue', $SessionId, $ClueId)
    Run-ProjectStep -Name 'session link faction' -Args @('session', 'link', 'faction', $SessionId, $FactionId)
    Run-ProjectStep -Name 'session link clock' -Args @('session', 'link', 'clock', $SessionId, $ClockId)

    Run-ProjectStep -Name 'writing create' -Args @('writing', 'create', 'Capitulo 1', '--type', 'capitulo', '--content', 'Borrador smoke', '--summary', 'Resumen smoke')

    @'
La Orden del Eclipse protege a Aria en la Torre Negra.
La Llave Solar podria abrir la puerta oculta durante la Sesion 1.
'@ | Set-Content -Path $ImportPath -Encoding utf8
    Assert-PathExists -Path $ImportPath -Message "Import file not created: $ImportPath"
    Run-ProjectStep -Name 'import document txt' -Args @('import', 'document', $ImportPath, '--format', 'txt')

    Run-ProjectStep -Name 'issue validate' -Args @('issue', 'validate')
    Run-ProjectStep -Name 'export public-summary' -Args @('export', 'public-summary', '--json')

    $project = Load-Project
    if (@($project.entities).Count -lt 4) { throw 'Smoke project has fewer than 4 entities' }
    if (@($project.relations).Count -lt 1) { throw 'Smoke project has no relations' }
    if (@($project.campaigns).Count -lt 1) { throw 'Smoke project has no campaigns' }
    if (@($project.sessions).Count -lt 1) { throw 'Smoke project has no sessions' }
    if (@($project.secrets).Count -lt 1) { throw 'Smoke project has no secrets' }
    if (@($project.clues).Count -lt 1) { throw 'Smoke project has no clues' }

    Write-Logged ""
    Write-Logged ('Smoke B27.3 OK')
    Write-Logged ("Project ready: {0}" -f $ProjectPath)
    Write-Logged ("Latest project path file: {0}" -f $LatestProjectPathFile)
    Write-Host 'Smoke B27.3 OK'
    Write-Host ("Project ready: {0}" -f $ProjectPath)
    Write-Host ("Latest project path file: {0}" -f $LatestProjectPathFile)
}
catch {
    Write-Logged ""
    Write-Logged ("Smoke B27.3 FAILED at step: {0}" -f $script:CurrentStep)
    Write-Logged ("ERROR: {0}" -f $_.Exception.Message)
    Write-Error ("Smoke B27.3 FAILED at step '{0}': {1}" -f $script:CurrentStep, $_.Exception.Message)
    exit 1
}
