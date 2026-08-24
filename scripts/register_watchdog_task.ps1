# Registers/re-registers the TBOT-Watchdog scheduled task: checks every 5 minutes
# whether TBOT-Arena / TBOT-Monitor are running and relaunches either if not (see
# watchdog.ps1 for why this exists -- Task Scheduler's own restart-on-failure doesn't
# reliably recover both tasks after this laptop's extended sleep/hibernate).
#
# Runs via watchdog_silent.vbs (wscript.exe, window style 0) instead of invoking
# powershell.exe directly, so it never flashes a visible console every 5 minutes.
#
# Safe to re-run any time -- it stops+re-registers the task, then starts it.
#
#   .\scripts\register_watchdog_task.ps1

$ErrorActionPreference = "Stop"

$taskName = "TBOT-Watchdog"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$vbsPath = Join-Path $projectRoot "scripts\watchdog_silent.vbs"

if (-not (Test-Path $vbsPath)) {
    throw "Could not find $vbsPath."
}

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -Hidden

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Every 5 minutes, silently relaunches TBOT-Arena/TBOT-Monitor if either isn't running. No visible window (runs via wscript.exe hidden)." | Out-Null

Write-Host "Registered and started '$taskName' (silent -- checks every 5 minutes, no visible window)."
