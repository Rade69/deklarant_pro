' ================================================================
' Deklarant Pro — Pokretanje bez terminala (za korisnike)
' Dvostruki klik pokrece aplikaciju bez vidljivog CMD prozora
' ================================================================

Dim appFolder, python, script

' Folder gdje se nalazi ovaj .vbs fajl
appFolder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Putanja do Python-a unutar .venv
python  = appFolder & "\.venv\Scripts\pythonw.exe"
script  = appFolder & "\run.py"

' Provjeri da li .venv postoji
If Not CreateObject("Scripting.FileSystemObject").FileExists(python) Then
    MsgBox "Okruzenje (.venv) nije pronadjeno!" & vbCrLf & vbCrLf & _
           "Pokreni prvo: setup_windows_venv.bat" & vbCrLf & vbCrLf & _
           "Putanja: " & appFolder, vbCritical, "Deklarant Pro"
    WScript.Quit 1
End If

' Pokreni aplikaciju bez terminala (0 = skriven prozor)
CreateObject("WScript.Shell").Run """" & python & """ """ & script & """", 0, False
