<#
.SYNOPSIS
    Agrege tokens, cout et duree par modele, par effort et par role depuis les
    transcripts JSONL d'une session Claude Code.

.DESCRIPTION
    Instrument de mesure du routage selectif. Produit un rapport dont le champ
    Complete vaut $true seulement si aucun diagnostic n'a ete leve. Un rapport
    incomplet a le statut "non observable" : ses tokens, couts et durees ne
    doivent jamais servir dans une comparaison economique.

    Arborescence lue, sous ~/.claude/projects/<slug-du-cwd>/ :
      <session>.jsonl                                 tours de l'agent racine
      <session>/subagents/agent-<id>.jsonl            tours de chaque sous-agent
      <session>/subagents/agent-<id>.meta.json        role et mode de lancement

    Deux pieges que ce script evite, verifies contre la facturation reelle :

    1. Un meme message apparait sur plusieurs enregistrements, un par bloc de
       contenu, et son `usage` est CUMULATIF. Retenir le premier sous-compte la
       sortie ; on retient donc le maximum par identifiant de message.
    2. `toolUseResult.usage` ne porte que le DERNIER tour d'un sous-agent, pas
       son cumul. La consommation reelle se lit dans son propre transcript.

.PARAMETER SessionsDir
    Dossier des transcripts. Par defaut, le dossier projet correspondant au
    repertoire courant sous ~/.claude/projects.

.PARAMETER SessionId
    Limite la lecture a cette session (nom de fichier sans extension).

.PARAMETER ExportPath
    Ecrit le rapport complet en JSON a ce chemin.

.PARAMETER PriceTable
    Table de prix de remplacement. Meme forme que $script:DefaultPrices.

.PARAMETER Quiet
    N'affiche rien sur la console.

.PARAMETER PassThru
    Retourne l'objet rapport sur le pipeline.

.NOTES
    Ecrit pour Windows PowerShell 5.1. NE PAS utiliser ConvertFrom-Json -Depth
    ici : le parametre n'existe pas dans cette version.
#>
[CmdletBinding()]
param(
    [string]   $SessionsDir,
    [string]   $SessionId,
    [string]   $ExportPath,
    [hashtable]$PriceTable,
    [switch]   $Quiet,
    [switch]   $PassThru
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# Tarifs en USD par million de tokens. Mettre a jour ici quand ils changent :
# c'est la seule source de verite du cout dans ce script.
# La cle est un prefixe d'identifiant de modele ; les identifiants dates
# (claude-haiku-4-5-20251001) sont apparies par prefixe le plus long.
#
# L'ecriture de cache se tarife selon sa duree de vie : 1,25x l'entree pour un
# cache de 5 minutes, 2x pour un cache d'une heure. Claude Code utilise les deux
# dans une meme session ; confondre les deux sous-compte la facture.
$script:DefaultPrices = @{
    'claude-fable-5-1' = @{ Input = 10.0; Output = 50.0; CacheWrite5m = 12.50; CacheWrite1h = 20.0; CacheRead = 0.25 }
    'claude-fable-5'   = @{ Input = 10.0; Output = 50.0; CacheWrite5m = 12.50; CacheWrite1h = 20.0; CacheRead = 0.25 }
    'claude-opus-5'    = @{ Input =  5.0; Output = 25.0; CacheWrite5m =  6.25; CacheWrite1h = 10.0; CacheRead = 0.50 }
    'claude-opus-4-8'  = @{ Input =  5.0; Output = 25.0; CacheWrite5m =  6.25; CacheWrite1h = 10.0; CacheRead = 0.50 }
    'claude-sonnet-5'  = @{ Input =  2.0; Output = 10.0; CacheWrite5m =  2.50; CacheWrite1h =  4.0; CacheRead = 0.20 }
    'claude-haiku-4-5' = @{ Input =  1.0; Output =  5.0; CacheWrite5m =  1.25; CacheWrite1h =  2.0; CacheRead = 0.10 }
}

function Get-Prop {
    # ConvertFrom-Json rend des PSCustomObject ; sous StrictMode, lire une
    # propriete absente leve. Ce helper rend $null a la place.
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    if ($Object -is [hashtable]) {
        if ($Object.ContainsKey($Name)) { return $Object[$Name] }
        return $null
    }
    $member = $Object.PSObject.Properties[$Name]
    if ($null -eq $member) { return $null }
    return $member.Value
}

function Get-Int {
    param($Value)
    if ($null -eq $Value) { return [int64]0 }
    try { return [int64]$Value } catch { return [int64]0 }
}

function Resolve-Price {
    param([string]$Model, [hashtable]$Prices)
    if ([string]::IsNullOrWhiteSpace($Model)) { return $null }
    $best = $null; $bestLen = -1
    foreach ($key in $Prices.Keys) {
        if ($Model -like "$key*" -and $key.Length -gt $bestLen) {
            $best = $Prices[$key]; $bestLen = $key.Length
        }
    }
    return $best
}

function Get-CostUsd {
    param([hashtable]$Price, [int64]$In, [int64]$Out,
          [int64]$CacheWrite5m, [int64]$CacheWrite1h, [int64]$CacheRead)
    if ($null -eq $Price) { return $null }
    $cost = ($In           / 1e6) * $Price.Input +
            ($Out          / 1e6) * $Price.Output +
            ($CacheWrite5m / 1e6) * $Price.CacheWrite5m +
            ($CacheWrite1h / 1e6) * $Price.CacheWrite1h +
            ($CacheRead    / 1e6) * $Price.CacheRead
    return [math]::Round($cost, 6)
}

function New-Bucket {
    param([string]$Key, [string]$Model, [string]$Effort, [string]$Kind)
    [pscustomobject]@{
        Key = $Key; Model = $Model; Effort = $Effort; Kind = $Kind
        Turns = 0; InputTokens = [int64]0; OutputTokens = [int64]0
        CacheWrite5mTokens = [int64]0; CacheWrite1hTokens = [int64]0
        CacheWriteTokens = [int64]0; CacheReadTokens = [int64]0
        DurationMs = [int64]0; ToolUses = [int64]0; CostUsd = $null
    }
}

function Read-Turns {
    <#
      Lit un transcript et rend un tableau de tours deduplique.

      Un message apparait une fois par bloc de contenu et son `usage` est
      cumulatif : on retient le maximum de chaque champ par identifiant de
      message. Retenir le premier sous-compterait la sortie.
    #>
    param([string]$Path, [System.Collections.ArrayList]$Diagnostics)

    $byId = @{}
    $name = Split-Path $Path -Leaf
    $lineNo = 0
    $reader = New-Object System.IO.StreamReader($Path, [System.Text.Encoding]::UTF8)
    try {
        while ($null -ne ($line = $reader.ReadLine())) {
            $lineNo++
            if ([string]::IsNullOrWhiteSpace($line)) { continue }

            $rec = $null
            try { $rec = ConvertFrom-Json $line } catch {
                [void]$Diagnostics.Add("$name`:$lineNo ligne JSON illisible")
                continue
            }
            if ((Get-Prop $rec 'type') -ne 'assistant') { continue }

            $msg = Get-Prop $rec 'message'
            $model = [string](Get-Prop $msg 'model')
            $usage = Get-Prop $msg 'usage'
            if (-not $model) {
                [void]$Diagnostics.Add("$name`:$lineNo tour assistant sans modele")
                continue
            }
            $in = Get-Prop $usage 'input_tokens'
            $out = Get-Prop $usage 'output_tokens'
            if ($null -eq $in -and $null -eq $out) {
                [void]$Diagnostics.Add("$name`:$lineNo tour assistant ($model) sans usage exploitable")
                continue
            }

            $total = Get-Int (Get-Prop $usage 'cache_creation_input_tokens')
            $cc = Get-Prop $usage 'cache_creation'
            $c5 = Get-Int (Get-Prop $cc 'ephemeral_5m_input_tokens')
            $c1 = Get-Int (Get-Prop $cc 'ephemeral_1h_input_tokens')
            if ($total -ne 0 -and (($null -eq $cc) -or (($c5 + $c1) -ne $total))) {
                [void]$Diagnostics.Add("$name`:$lineNo tour ($model) : $total tokens d'ecriture de cache sans ventilation par duree de vie ; tarif inconnu (1,25x ou 2x l'entree)")
                continue
            }

            $id = [string](Get-Prop $msg 'id')
            if (-not $id) { $id = "$name`:$lineNo" }
            $effort = [string](Get-Prop $rec 'effort')
            if (-not $effort) { $effort = '(non renseigne)' }

            if (-not $byId.ContainsKey($id)) {
                $byId[$id] = [pscustomobject]@{
                    Model = $model; Effort = $effort
                    In = [int64]0; Out = [int64]0
                    C5 = [int64]0; C1h = [int64]0; CR = [int64]0
                }
            }
            $t = $byId[$id]
            $t.In  = [Math]::Max($t.In,  (Get-Int $in))
            $t.Out = [Math]::Max($t.Out, (Get-Int $out))
            $t.C5  = [Math]::Max($t.C5,  $c5)
            $t.C1h = [Math]::Max($t.C1h, $c1)
            $t.CR  = [Math]::Max($t.CR,  (Get-Int (Get-Prop $usage 'cache_read_input_tokens')))
        }
    } finally { $reader.Dispose() }

    return @($byId.Values)
}

function Add-Turns {
    param($Buckets, [array]$Turns, [string]$Key, [string]$Kind)
    foreach ($t in $Turns) {
        $bk = "$Key|$($t.Model)|$($t.Effort)"
        if (-not $Buckets.ContainsKey($bk)) {
            $Buckets[$bk] = New-Bucket -Key $Key -Model $t.Model -Effort $t.Effort -Kind $Kind
        }
        $b = $Buckets[$bk]
        $b.Turns              += 1
        $b.InputTokens        += $t.In
        $b.OutputTokens       += $t.Out
        $b.CacheWrite5mTokens += $t.C5
        $b.CacheWrite1hTokens += $t.C1h
        $b.CacheWriteTokens   += ($t.C5 + $t.C1h)
        $b.CacheReadTokens    += $t.CR
    }
}

# --- Resolution du dossier de sessions -------------------------------------

if ([string]::IsNullOrWhiteSpace($SessionsDir)) {
    # Claude Code remplace les separateurs et ':' du chemin par '-'.
    $slug = (Get-Location).Path -replace '[\\/:]', '-'
    $SessionsDir = Join-Path $env:USERPROFILE ".claude\projects\$slug"
}
if (-not (Test-Path -LiteralPath $SessionsDir)) {
    throw "Dossier de sessions introuvable : $SessionsDir"
}

$files = @(Get-ChildItem -LiteralPath $SessionsDir -Filter '*.jsonl' -File)
if ($SessionId) { $files = @($files | Where-Object { $_.BaseName -eq $SessionId }) }
if ($files.Count -eq 0) { throw "Aucun transcript .jsonl dans $SessionsDir" }

$prices = if ($PriceTable) { $PriceTable } else { $script:DefaultPrices }

# --- Lecture ----------------------------------------------------------------

$diagnostics = New-Object System.Collections.ArrayList
$buckets     = @{}
$sessions    = New-Object System.Collections.ArrayList

foreach ($file in $files) {
    # Tours de l'agent racine.
    $rootTurns = @(Read-Turns -Path $file.FullName -Diagnostics $diagnostics)
    Add-Turns -Buckets $buckets -Turns $rootTurns -Key 'racine' -Kind 'racine'

    # Metriques d'appel (duree, outils, statut) depuis le transcript racine.
    $calls = @{}
    $reader = New-Object System.IO.StreamReader($file.FullName, [System.Text.Encoding]::UTF8)
    try {
        $lineNo = 0
        while ($null -ne ($line = $reader.ReadLine())) {
            $lineNo++
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $rec = $null
            try { $rec = ConvertFrom-Json $line } catch { continue }
            $tur = Get-Prop $rec 'toolUseResult'
            $agentId = Get-Prop $tur 'agentId'
            if ($null -eq $agentId) { continue }
            $status = [string](Get-Prop $tur 'status')
            if ($status -eq 'async_launched') {
                if (-not $calls.ContainsKey([string]$agentId)) {
                    $calls[[string]$agentId] = @{ Status = 'lance'; DurationMs = [int64]0; ToolUses = [int64]0 }
                }
                continue
            }
            $calls[[string]$agentId] = @{
                Status     = $status
                DurationMs = Get-Int (Get-Prop $tur 'totalDurationMs')
                ToolUses   = Get-Int (Get-Prop $tur 'totalToolUseCount')
            }
            if ($status -and $status -ne 'completed') {
                [void]$diagnostics.Add("$($file.Name):$lineNo sous-agent '$(Get-Prop $tur 'agentType')' statut '$status' (non observable)")
            }
        }
    } finally { $reader.Dispose() }

    # Tours des sous-agents : leur consommation reelle vit dans leur propre
    # transcript, pas dans le resultat d'appel.
    $subDir = Join-Path $SessionsDir "$($file.BaseName)\subagents"
    $agentCalls = 0
    $seenAgents = @{}
    if (Test-Path -LiteralPath $subDir) {
        foreach ($sub in @(Get-ChildItem -LiteralPath $subDir -Filter 'agent-*.jsonl' -File)) {
            $agentCalls++
            $agentId = $sub.BaseName -replace '^agent-', ''
            $seenAgents[$agentId] = $true

            $role = $agentId; $shape = 'inconnu'
            $metaPath = Join-Path $subDir "$($sub.BaseName).meta.json"
            if (Test-Path -LiteralPath $metaPath) {
                try {
                    $meta = ConvertFrom-Json ((Get-Content -LiteralPath $metaPath -Raw))
                    $t = [string](Get-Prop $meta 'agentType')
                    if ($t) { $role = $t }
                    $s = [string](Get-Prop $meta 'requestShape')
                    if ($s) { $shape = $s }
                } catch {
                    [void]$diagnostics.Add("$($sub.BaseName).meta.json illisible ; role non attribuable")
                }
            } else {
                [void]$diagnostics.Add("$($sub.BaseName) sans meta.json ; role non attribuable")
            }

            $turns = @(Read-Turns -Path $sub.FullName -Diagnostics $diagnostics)
            if ($turns.Count -eq 0) {
                [void]$diagnostics.Add("sous-agent '$role' ($($sub.BaseName)) : transcript sans tour exploitable")
                continue
            }
            Add-Turns -Buckets $buckets -Turns $turns -Key $role -Kind "sous-agent ($shape)"

            if ($calls.ContainsKey($agentId)) {
                $bk = "$role|$($turns[0].Model)|$($turns[0].Effort)"
                if ($buckets.ContainsKey($bk)) {
                    $buckets[$bk].DurationMs += [int64]$calls[$agentId].DurationMs
                    $buckets[$bk].ToolUses   += [int64]$calls[$agentId].ToolUses
                }
            }
        }
    }

    # Un sous-agent lance dont le transcript est absent laisse un trou.
    foreach ($id in $calls.Keys) {
        if (-not $seenAgents.ContainsKey($id)) {
            [void]$diagnostics.Add("sous-agent $id lance sans transcript dans $($file.BaseName)\subagents ; consommation inconnue")
        }
    }

    [void]$sessions.Add([pscustomobject]@{
        SessionId = $file.BaseName
        RootTurns = $rootTurns.Count
        AgentCalls = $agentCalls
    })
}

# --- Cout -------------------------------------------------------------------

$rows = @()
foreach ($b in $buckets.Values) {
    $price = Resolve-Price -Model $b.Model -Prices $prices
    if ($null -eq $price) {
        [void]$diagnostics.Add("modele '$($b.Model)' absent de la table de prix ; cout non calculable")
    } else {
        $b.CostUsd = Get-CostUsd -Price $price -In $b.InputTokens -Out $b.OutputTokens `
                                 -CacheWrite5m $b.CacheWrite5mTokens `
                                 -CacheWrite1h $b.CacheWrite1hTokens `
                                 -CacheRead $b.CacheReadTokens
    }
    $rows += $b
}
$rows = @($rows | Sort-Object -Property @{Expression={$_.Kind}}, @{Expression={$_.CostUsd}; Descending=$true})

$totalCost = $null
if ($rows.Count -gt 0 -and -not ($rows | Where-Object { $null -eq $_.CostUsd })) {
    $totalCost = [math]::Round((($rows | Measure-Object -Property CostUsd -Sum).Sum), 6)
}

$report = [pscustomobject]@{
    SchemaVersion = 2
    GeneratedAt   = (Get-Date).ToString('o')
    SessionsDir   = $SessionsDir
    Sessions      = @($sessions)
    Buckets       = $rows
    TotalCostUsd  = $totalCost
    Diagnostics   = @($diagnostics)
    Complete      = ($diagnostics.Count -eq 0)
}

if ($ExportPath) {
    $report | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $ExportPath -Encoding utf8
}

if (-not $Quiet) {
    Write-Output ""
    Write-Output "Sessions lues : $($sessions.Count)   dossier : $SessionsDir"
    $rows | Format-Table -AutoSize Key, Model, Effort, Kind, Turns, InputTokens, OutputTokens,
                                   CacheWrite5mTokens, CacheWrite1hTokens, CacheReadTokens,
                                   ToolUses, DurationMs, CostUsd |
        Out-String | Write-Output
    if ($null -ne $totalCost) { Write-Output ("Cout total : {0:N4} USD" -f $totalCost) }
    else { Write-Output "Cout total : non calculable" }
    Write-Output "Complete : $($report.Complete)"
    if ($diagnostics.Count -gt 0) {
        Write-Output ""
        Write-Output "Diagnostics ($($diagnostics.Count)) - rapport NON OBSERVABLE, ne pas l'utiliser"
        Write-Output "dans une comparaison economique :"
        foreach ($d in $diagnostics) { Write-Output "  - $d" }
    }
}

if ($PassThru) { $report }
