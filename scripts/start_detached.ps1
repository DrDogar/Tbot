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
$pythonwExe = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonwExe)) {
    throw "Could not find venv pythonw at $pythonwExe. Create the venv first."
}

function Register-DetachedTask($taskName, $scriptFile) {
    $scriptPath = Join-Path $projectRoot $scriptFile

    if (-not (Test-Path $scriptPath)) {
        throw "Could not find $scriptPath."
    }

    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Start-Sleep -Seconds 1
    }

    # Uses pythonw.exe (the windowless build of the interpreter), launched directly
    # as the task's own action -- not the run_hidden.vbs/wscript.exe wrapper tried
    # earlier, which broke Stop-ScheduledTask's ability to kill the real process (it
    # only killed the wrapper, leaving python.exe orphaned; verified two arenas ran
    # against the same portfolio files at once because of it). pythonw.exe never
    # allocates a console at all, so there's no window to hide, and Task Scheduler
    # tracks it as its own direct child exactly like python.exe -- Stop-ScheduledTask
    # kill semantics verified identical (tested standalone, and with a throwaway
    # Flask instance under Task Scheduler, before rolling this out here). The only
    # difference at the code level: sys.stdout/stderr are None under pythonw.exe --
    # verified both logging (file handler works, console handler no-ops safely) and
    # print() (also a safe no-op) tolerate that; nothing in these two scripts writes
    # to a console in a way that assumes it exists.
    $action = New-ScheduledTaskAction -Execute $pythonwExe -Argument "`"$scriptPath`"" -WorkingDirectory $projectRoot
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
# console window every check) so there's exactly one place that defines it.
& (Join-Path $projectRoot "scripts\register_watchdog_task.ps1")

Write-Host ""
Write-Host "Both tasks registered and started. They will keep running (and auto-restart on crash"
Write-Host "or after this laptop wakes from sleep) even if this terminal, Claude Code, or VS Code is closed."
Write-Host ""
Write-Host "Check status:  Get-ScheduledTask -TaskName 'TBOT-Arena','TBOT-Monitor','TBOT-Watchdog' | Get-ScheduledTaskInfo"
Write-Host "Stop them:     Stop-ScheduledTask -TaskName 'TBOT-Arena'; Stop-ScheduledTask -TaskName 'TBOT-Monitor'; Stop-ScheduledTask -TaskName 'TBOT-Watchdog'"
