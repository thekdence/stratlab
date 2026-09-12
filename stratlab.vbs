Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Vault\Python Projects\strat-lab"
WshShell.Run "cmd.exe /c """ & WshShell.CurrentDirectory & "\stratlab.bat""", 0, False
