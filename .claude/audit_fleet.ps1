# Run several audit passes at once, each in its own git worktree.
#
# One agent doing one pass at a time is bounded by how long a pass takes, not by how much
# there is to audit — twenty targets and sixteen mutation modules is weeks of sequential
# passes. Workers get separate worktrees so they can edit the same repo without racing, and
# separate offsets so `audit_next.py` hands each of them a different target.
#
#   .\.claude\audit_fleet.ps1 -Workers 3 -Rounds 5
#   .\.claude\audit_fleet.ps1 -Workers 4 -Command 'hermes -p'
#
# Merges happen here, one at a time, in the main repo. Workers never merge and never touch
# the shared log: they leave a row in their own .claude/records/ and this collects them, which
# is the difference between a fleet that converges and four agents fighting over one table.

param(
    [int]    $Workers = 3,
    [int]    $Rounds  = 0,                 # 0 = until stopped
    [string] $Command = 'claude -p',
    [int]    $TimeoutMinutes = 60
)

# Continue, not Stop: in Windows PowerShell a native command writing to stderr - which git
# does for ordinary progress lines like "Preparing worktree" - is surfaced as a
# NativeCommandError, and under Stop that aborts the run on a message that was not an error.
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$promptTemplate = @'
Read .claude/audit-loop.md and follow it for ONE pass, then stop.
Get your assignment with: python .claude/audit_next.py --offset {0}
Record it with: python .claude/audit_next.py record --offset {0} --worker {1} ...
Do NOT edit .claude/audit-log.md or .claude/survivors.md - the fleet runner owns those.
Run `python .claude/guard.py` before every commit; if it blocks, the commit is not yours to
make. Commit to this worktree's branch. Do not merge, do not push.
Recording `clean` is a correct outcome. Never invent a finding.
'@

function Merge-Worker([string]$branch, [string]$tree, [int]$idx) {
    # Rows first: a merge conflict must not cost the record of what the worker actually did.
    $records = Join-Path $tree '.claude\records'
    if (Test-Path $records) {
        Get-ChildItem $records -Filter '*.row' | ForEach-Object {
            Add-Content -Path '.\.claude\audit-log.md' -Value (Get-Content $_.FullName -Raw).TrimEnd() -Encoding utf8
            Remove-Item $_.FullName -Force
        }
    }

    $ahead = (git rev-list --count "main..$branch") 2>$null
    if ([string]::IsNullOrWhiteSpace($ahead) -or $ahead -eq '0') {
        Write-Output "  w$idx : no commits, nothing to merge"
        return
    }
    git merge --no-ff --no-edit $branch | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  w$idx : merged $ahead commit(s)"
    } else {
        # Abort rather than resolve. A conflict means two passes touched the same lines, and
        # picking a side unattended is exactly the class of change the envelope forbids.
        git merge --abort | Out-Null
        Write-Output "  w$idx : CONFLICT - left on $branch, not merged"
        Add-Content -Path '.\.claude\human-queue.md' -Encoding utf8 -Value @"

## fleet AMBER - worker $idx conflicted on merge

WHAT   $ahead commit(s) on ``$branch`` conflict with main and were not merged.
RAN    git merge --no-ff $branch
SAW    conflict; merge aborted, branch left intact
NEXT   merge it by hand, or delete the branch if the work was superseded.
"@
    }
}

$round = 0
while ($Rounds -eq 0 -or $round -lt $Rounds) {
    $round++
    git worktree prune | Out-Null
    Write-Output "=== fleet round $round  ($Workers workers)  $(Get-Date -Format s) ==="

    $jobs = @()
    for ($k = 0; $k -lt $Workers; $k++) {
        $tree   = Join-Path $repo ".claude\worktrees\w$k"
        $branch = "loop/w$k"
        # -B resets the branch to main each round, so a worker always starts from what the
        # previous round merged rather than from its own stale history.
        git worktree add -B $branch $tree main | Out-Null
        if (-not (Test-Path $tree)) {
            Write-Output "  w$k : could not create worktree, skipping"
            continue
        }
        $jobs += Start-Job -Name "w$k" -ScriptBlock {
            param($cmd, $p, $wd)
            Set-Location $wd
            Invoke-Expression "$cmd `"$($p -replace '"', '\"')`""
        } -ArgumentList $Command, ($promptTemplate -f $k, "w$k"), $tree
    }

    foreach ($job in $jobs) {
        if (Wait-Job $job -Timeout ($TimeoutMinutes * 60)) { Receive-Job $job | Out-Null }
        else { Write-Output "  $($job.Name) : over $TimeoutMinutes min, killed"; Stop-Job $job }
        Remove-Job $job -Force
    }

    Write-Output '--- merging ---'
    for ($k = 0; $k -lt $Workers; $k++) {
        Merge-Worker "loop/w$k" (Join-Path $repo ".claude\worktrees\w$k") $k
    }

    git add .claude/audit-log.md .claude/human-queue.md | Out-Null
    # `--quiet` exits 1 when there IS something staged, which is the signal we want.
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "chore(loop): record round $round" | Out-Null
        git push origin main | Out-Null
    }

    Write-Output '--- log tail ---'
    Get-Content .\.claude\audit-log.md -Tail 4
}
