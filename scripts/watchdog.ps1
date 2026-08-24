# Runs every few minutes (via the TBOT-Watchdog scheduled task) and relaunches
# TBOT-Arena / TBOT-Monitor if either isn't in the "Running" state.
#
# Why this exists: Task Scheduler's own restart-on-failure setting doesn't reliably
# bring these back after this laptop does an extended sleep/hibernate -- both tasks
# have been observed sitting "Ready" (i.e. dead) for over a day after a long sleep,
# with no automatic recovery. This is the safety net for that case. Both scripts are
# resumable from state/, so relaunching just picks up where they left off.

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$logPath = Join-Path $projectRoot "state\watchdog.log"

foreach ($taskName in @("TBOT-Arena", "TBOT-Monitor")) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

    if ($null -eq $task) {
        continue
    }

    if ($task.State -ne "Running") {
        Start-ScheduledTask -TaskName $taskName
        Add-Content -Path $logPath -Value "$(Get-Date -Format o) | Watchdog restarted $taskName (was $($task.State))"
    }
}
