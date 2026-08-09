# One-line installer for the untell Claude Code skill (Windows PowerShell).
#   irm https://raw.githubusercontent.com/ssamba1/untell/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

# Source repo; override with $env:UNTELL_REPO (a URL or a local path) — used by CI to
# install from the checked-out copy instead of the published main branch.
$repo = if ($env:UNTELL_REPO) { $env:UNTELL_REPO } else { "https://github.com/ssamba1/untell" }
$skillsDir = if ($env:CLAUDE_SKILLS_DIR) { $env:CLAUDE_SKILLS_DIR } else { Join-Path $env:USERPROFILE ".claude\skills" }
$dest = Join-Path $skillsDir "untell"
$tmp  = Join-Path $env:TEMP ("untell-" + [guid]::NewGuid().ToString())

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "git is required."
}

Write-Host "Fetching untell..."
# Run git with ErrorActionPreference relaxed: PowerShell 5.1 turns git's stderr
# progress ("Cloning into ...") into a terminating NativeCommandError otherwise.
# The native exit code is the real success signal.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git clone --depth 1 --quiet $repo $tmp 2>&1 | Out-Null
$cloneExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($cloneExit -ne 0) { Write-Error "git clone failed (exit $cloneExit)." }

# try/finally so the temp clone is removed even when the copy fails. install.sh has had this
# since it was written (`trap cleanup EXIT`); this side removed $tmp only on the success path, so
# a failed Copy-Item left a full repository clone in %TEMP% with nothing to indicate why.
try {
  New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
  if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
  Copy-Item -Recurse (Join-Path $tmp "untell") $dest
} finally {
  if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
}

Write-Host ""
Write-Host "  Installed the untell skill -> $dest"
Write-Host ""
Write-Host "  Use it in Claude Code:   /untell <your text or a file path>"
Write-Host "  Real detector ensemble:  see https://github.com/ssamba1/untell#tiers"
Write-Host ""
