#define MyAppName "DocPilot"
#define MyAppVersion "0.7.0"
#define MyAppPublisher "Łukasz Staniewicz"
#define MyAppExeName "DocPilot.exe"

[Setup]
AppId={{8D7A3D8B-25C3-47C7-A65E-DOCPILOT040}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\DocPilot
DefaultGroupName=DocPilot
OutputDir=..\..\dist-installer
OutputBaseFilename=DocPilot-Setup-Windows-x64
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\DocPilot.exe

[Files]
Source: "..\..\dist\DocPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DocPilot"; Filename: "{app}\DocPilot.exe"
Name: "{autodesktop}\DocPilot"; Filename: "{app}\DocPilot.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "notifications"; Description: "Start DocPilot deadline notifications when I sign in"; GroupDescription: "Background features:"; Flags: unchecked

[Run]
Filename: "{app}\DocPilotNotifier.exe"; Parameters: "--install-startup"; Flags: runhidden waituntilterminated; Tasks: notifications
Filename: "{app}\DocPilot.exe"; Description: "Launch DocPilot"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\DocPilotNotifier.exe"; Parameters: "--remove-startup"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveDocPilotNotifierTask"
