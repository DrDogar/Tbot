' Generic hidden launcher: runs "python.exe <ScriptFile>" from the project root with
' a fully hidden window (style 0), waits for it to exit, and passes its exit code
' back through -- so Task Scheduler's restart-on-failure still sees real crashes.
'
' Usage (from a Scheduled Task action): wscript.exe run_hidden.vbs run_arena.py
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(scriptDir)
pythonExe = projectRoot & "\.venv\Scripts\python.exe"
targetScript = projectRoot & "\" & WScript.Arguments(0)

Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = projectRoot
exitCode = objShell.Run("""" & pythonExe & """ """ & targetScript & """", 0, True)
WScript.Quit(exitCode)
