# Run the untell audit loop continuously.
#
# One iteration = one pass = one fresh agent context. That boundary is the point: a small
# model degrades over a long session, and a pass that carries yesterday's half-conclusions
# forward is how a loop starts confirming its own mistakes. Each pass reads its assignment
# from audit_next.py, which holds the only state that survives.
#
#   .\.claude\audit_loop.ps1                       # run until stopped
#   .\.claude\audit_loop.ps1 -Passes 20            # bounded run
#   .\.claude\audit_loop.ps1 -Command 'hermes -p'  # any agent CLI that takes a prompt

param(
    [int]    $Passes  = 0,                                  # 0 = until stopped
    [string] $Command = 'claude -p',
    [int]    $CooldownSeconds = 30
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$prompt = @'
Read .claude/audit-loop.md and follow it exactly for ONE pass, then stop.
Run `.venv/Scripts/python.exe .claude/audit_next.py` first to get your assignment.
Record the pass with `audit_next.py record` and push before you finish.
Recording `clean` is a correct outcome. Never invent a finding.
'@

$i = 0
while ($Passes -eq 0 -or $i -lt $Passes) {
    $i++
    Write-Output "=== audit pass iteration $i  $(Get-Date -Format s) ==="

    # A pass that hangs or loops on a stuck probe must not stall the queue behind it; the next
    # iteration gets a different target anyway, so killing this one loses one pass, not the run.
    $job = Start-Job -ScriptBlock {
        param($cmd, $p, $wd)
        Set-Location $wd
        Invoke-Expression "$cmd `"$($p -replace '"', '\"')`""
    } -ArgumentList $Command, $prompt, $repo

    if (Wait-Job $job -Timeout 3600) {
        Receive-Job $job
    } else {
        Write-Output "!!! pass $i exceeded 60 minutes - killed, moving on"
        Stop-Job $job
    }
    Remove-Job $job -Force

    # Surface what the pass actually recorded, so a run left unattended still reads back as a
    # ledger rather than as a wall of agent chatter.
    Write-Output '--- log tail ---'
    Get-Content .\.claude\audit-log.md -Tail 3

    if ($Passes -eq 0 -or $i -lt $Passes) { Start-Sleep -Seconds $CooldownSeconds }
}
