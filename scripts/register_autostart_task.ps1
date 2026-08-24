# Registers a Windows Scheduled Task that (re)launches the TBOT 24h session
# at every logon and keeps retrying if it stops (e.g. the laptop shuts off
# mid-session). The session itself is resumable, so a relaunch always picks
# up from the last saved checkpoint in state/.
#
# This script only REGISTERS the task -- it does not run it immediately.
# Review it, then run it yourself from a PowerShell prompt in this folder:
#   .\scripts\register_autostart_task.ps1

$ErrorActionPreference = "Stop"

$taskName = "TBOT-24h-session"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$scriptPath = Join-Path $projectRoot "run_session.py"

if (-not (Test-Path $pythonExe)) {
    throw "Could not find venv python at $pythonExe. Create the venv first."
}

if (-not (Test-Path $scriptPath)) {
    throw "Could not find $scriptPath."
}

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`"" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 30)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Resumes the TBOT 24h multi-coin paper trading session automatically after login/reboot." `
    -Force

Write-Host "Scheduled task '$taskName' registered."
Write-Host "It will start run_session.py at every logon and auto-retry if the process stops."
Write-Host "To remove it later: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
