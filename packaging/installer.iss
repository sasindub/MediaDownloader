; Inno Setup script for Media Downloader.
; Wraps the PyInstaller onefile exe in a normal Windows installer so users
; get a Start menu entry and a clean uninstall.

#define AppName "Media Downloader"
#define AppVersion "1.1.0"
#define AppPublisher "Sasindu Bandara"
#define AppExe "MediaDownloader.exe"

[Setup]
AppId={{8F2A4C61-9E3D-4B7A-A1C5-2D6E8F0B3A94}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=MediaDownloader-Windows-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Per user install by default, so no admin prompt is needed
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
LicenseFile=..\bin\FFMPEG-LICENCE.txt
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\bin\FFMPEG-LICENCE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
