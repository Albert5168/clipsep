; Inno Setup script: wraps dist\ClipSep into Setup.exe
#define AppName "剪報圖片文字分離編輯器"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6C1E8B0B-3F5E-4C55-9D0A-2B7E6A1C5F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=東港養殖研究中心
DefaultDirName={autopf}\ClipSep
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=ClipSep-Setup-{#AppVersion}
SetupIconFile=..\assets\app.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Languages]
Name: "cht"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\ClipSep\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ClipSep.exe"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ClipSep.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ClipSep.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
