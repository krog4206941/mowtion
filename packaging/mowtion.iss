; Inno Setup script. Compiled on the Windows release builder.
; Output: dist/mowtion-setup.exe

#define AppName "mowtion"
#define AppVersion "0.1.0"
#define AppPublisher "mowtion"
#define AppURL "https://github.com/krog4206941/mowtion"

[Setup]
AppId={{A7B3E1C4-6D20-4F5A-9C11-2E8D4B7A01F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\mowtion
DefaultGroupName=mowtion
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=mowtion-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\mowtion.exe

[Files]
Source: "..\dist\mowtion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\mowtion"; Filename: "{app}\mowtion.exe"
Name: "{autodesktop}\mowtion"; Filename: "{app}\mowtion.exe"

[Run]
Filename: "{app}\mowtion.exe"; Description: "Open mowtion"; Flags: nowait postinstall skipifsilent
