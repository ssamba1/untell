# One-line installer for the untell Claude Code skill (Windows PowerShell).
#   irm https://raw.githubusercontent.com/ssamba1/untell/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$repo = "https://github.com/ssamba1/untell"
$skillsDir = if ($env:CLAUDE_SKILLS_DIR) { $env:CLAUDE_SKILLS_DIR } else { Join-Path $env:USERPROFILE ".claude\skills" }
$dest = Join-Path $skillsDir "untell"
$tmp  = Join-Path $env:TEMP ("untell-" + [guid]::NewGuid().ToString())

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "git is required."
}

Write-Host "Fetching untell..."
git clone --depth 1 $repo $tmp 2>$null | Out-Null

New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Copy-Item -Recurse (Join-Path $tmp "untell") $dest
Remove-Item -Recurse -Force $tmp

Write-Host ""
Write-Host "  Installed the untell skill -> $dest"
Write-Host ""
Write-Host "  Use it in Claude Code:   /untell <your text or a file path>"
Write-Host "  Real detector ensemble:  see https://github.com/ssamba1/untell#tiers"
Write-Host ""
