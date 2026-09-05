#define MyAppName "PII Log Cleaner"
#define MyAppVersion "1.1.0"
#define MyAppExeName "PII.exe"

[Setup]
AppId={{B3E5432B-07DF-44ED-97DE-06BA2C3D0C32}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PII Log Cleaner
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PII-Log-Cleaner-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
SetupIconFile=..\resources\icons\branding\pii-log-cleaner-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\build\p\PII\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로 가기 만들기"; GroupDescription: "추가 작업:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} 실행"; Flags: nowait postinstall skipifsilent
