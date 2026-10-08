; Baldur 1.0.0 installer (Inno Setup 6).
; Per-user install, no admin rights required. Bundles the self-contained
; Warning app plus the frozen Recognition engine (Python embedded).
; Unsigned build: SmartScreen/Defender warnings on first install are
; expected until a code-signing certificate is procured (see #11).

#define MyAppName "Baldur"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Baldur"
#define MyAppExeName "Baldur.exe"

[Setup]
AppId={{111ab4b6-a1f6-4153-8786-fdaf7079fe07}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
PrivilegesRequired=lowest
OutputDir=B:\baldur-dist
OutputBaseFilename=BaldurSetup-1.0.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; No autostart by default: the app is started manually per project.md.
; An optional Startup shortcut is offered as an unchecked task below.

[Files]
Source: "B:\baldur-publish\warning\Baldur.exe"; DestDir: "{app}\Baldur"; Flags: ignoreversion
Source: "B:\baldur-dist\engine\*"; DestDir: "{app}\Baldur\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Baldur\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Baldur\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; Flags: unchecked
Name: "startupicon"; Description: "Start Baldur with Windows &startup"; Flags: unchecked

[Icons]
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\Baldur\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\Baldur\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall unchecked skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; Per-user config in %APPDATA%\Baldur is intentionally kept on uninstall.
