; =========================================================
;  Deklarant Pro — Inno Setup Installer Script
;  Preuzmi Inno Setup: https://jrsoftware.org/isdl.php
;  Kompajlira: iscc setup.iss
; =========================================================

#define AppName      "Deklarant Pro"
#define AppVersion   "1.0.0"
#define AppPublisher "Deklarant Pro"
#define AppExeName   "DeklarantPro.exe"
#define AppIcon      "..\assets\icons\deklarant_icon.ico"
#define SourceDir    "..\dist\DeklarantPro"

[Setup]
AppId={{8F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\DeklarantPro
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=DeklarantPro_Setup_v{#AppVersion}
SetupIconFile={#AppIcon}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

; Splash slika (opciono - 164x314 BMP)
; WizardImageFile=wizard_banner.bmp

[Languages]
Name: "bosnian"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Napravi prečicu na radnoj površini"; GroupDescription: "Prečice:"; Flags: unchecked

[Files]
; Svi fajlovi iz dist foldera
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; .env.example -> kopiraj kao .env ako .env ne postoji
Source: "{#SourceDir}\.env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icons\deklarant_icon.ico"
Name: "{group}\Deinstaliraj {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icons\deklarant_icon.ico"; Tasks: desktopicon

[Run]
; Otvori .env editor odmah nakon instalacije
Filename: "notepad.exe"; Parameters: "{app}\.env"; Description: "Konfiguriši bazu podataka (.env)"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Obrisi generisane fajlove pri deinstalaciji
Type: filesandordirs; Name: "{app}\data\knowledge_base\declaration_index.db"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
// Provjeri da li je .NET/Visual C++ Redistributable prisutan
// (psycopg2 može zahtijevati VCRUNTIME)
procedure InitializeWizard;
begin
  // Provjeri minimalnu verziju Windowsa
  if not IsWin64 then begin
    MsgBox('Deklarant Pro zahtijeva 64-bitni Windows 10 ili noviji.', mbError, MB_OK);
    Abort;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  EnvFile: String;
begin
  Result := True;
  // Na zadnjoj stranici podsjeti korisnika na konfiguraciju
  if CurPageID = wpFinished then begin
    EnvFile := ExpandConstant('{app}\.env');
    if FileExists(EnvFile) then begin
      // .env postoji — OK
    end;
  end;
end;
