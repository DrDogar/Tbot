# Launches the arena (run_arena.py) and the web monitor (run_monitor.py) as
# Windows Scheduled Tasks instead of plain child processes.
#
# Why: when they run as normal child processes of a terminal/Claude Code
# session, closing or recycling that session kills them with no error logged
# -- both the arena and portfolio state are checkpointed, so nothing is lost,
# but it means someone has to notice and manually restart every time. A
# Scheduled Task runs under its own process tree, independent of whatever
# terminal launched it, and Windows will auto-restart it if it crashes.
#
# Safe to re-run: it stops+re-registers the tasks each time, then starts
# them. Both scripts are resumable from state/, so a relaunch just picks up
# where the last one left off.
#
# Explicitly allowed to run on battery: Task Scheduler's default settings
# refuse to start (or instantly kill) a task while unplugged, which would
# silently break this on a laptop.
#
#   .\scripts\start_detached.ps1

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Could not find venv python at $pythonExe. Create the venv first."
}

function Register-DetachedTask($taskName, $scriptFile) {
    $scriptPath = Join-Path $projectRoot $scriptFile

    if (-not (Test-Path $scriptPath)) {
        throw "Could not find $scriptPath."
    }

    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`"" -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable `
        -DontStopOnIdleEnd `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
        -Description "Runs $scriptFile detached from any terminal/IDE session so it survives Claude Code / VSCode restarts. Resumes from state/ checkpoints." | Out-Null

    Start-ScheduledTask -TaskName $taskName
    Write-Host "Started detached task '$taskName' -> $scriptFile"
}

Register-DetachedTask "TBOT-Arena" "run_arena.py"
Register-DetachedTask "TBOT-Monitor" "run_monitor.py"

# Watchdog: Task Scheduler's own restart-on-failure doesn't reliably bring the two
# tasks above back after this laptop does an extended sleep/hibernate (observed one
# sitting dead for over a day after a ~25h sleep with no auto-recovery). Registration
# lives in its own script (runs the check via a hidden wscript.exe wrapper -- no visible
# console window every 5 minutes) so there's exactly one place that defines it.
& (Join-Path $projectRoot "scripts\register_watchdog_task.ps1")

Write-Host ""
Write-Host "Both tasks registered and started. They will keep running (and auto-restart on crash"
Write-Host "or after this laptop wakes from sleep) even if this terminal, Claude Code, or VS Code is closed."
Write-Host ""
Write-Host "Check status:  Get-ScheduledTask -TaskName 'TBOT-Arena','TBOT-Monitor','TBOT-Watchdog' | Get-ScheduledTaskInfo"
Write-Host "Stop them:     Stop-ScheduledTask -TaskName 'TBOT-Arena'; Stop-ScheduledTask -TaskName 'TBOT-Monitor'; Stop-ScheduledTask -TaskName 'TBOT-Watchdog'"
