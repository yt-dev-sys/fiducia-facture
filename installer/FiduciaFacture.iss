#define MyAppName "Fiducia Facture"
#define MyAppVersion "0.0.0"
#define MyAppPublisher "Fiducia Facture"
#define MyAppExeName "Fiducia Facture.exe"

[Setup]
AppId={{C6F4B5E5-9D15-4E1A-9D2E-7D5A5A2C1A01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Fiducia Facture
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=FiduciaFacture-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=yes

[Files]
Source: "..\dist\Fiducia Facture\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data is intentionally outside {app} and is never deleted by uninstall.
