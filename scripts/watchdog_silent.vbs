' Launches watchdog.ps1 with a fully hidden window (style 0) instead of the
' brief console flash Task Scheduler gives a direct powershell.exe action.
' True = wait for it to finish before this script (and the task run) ends.
Set objShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
psScript = scriptDir & "\watchdog.ps1"
objShell.Run "powershell.exe -ExecutionPolicy Bypass -NonInteractive -File """ & psScript & """", 0, True
