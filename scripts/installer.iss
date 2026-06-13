#define MyAppName GetEnv("PDF_IMG_APP_NAME")
#define MyAppVersion GetEnv("PDF_IMG_APP_VERSION")
#define MyBuildName GetEnv("PDF_IMG_BUILD_NAME")
#define MySourceDir GetEnv("PDF_IMG_SOURCE_DIR")
#define MyOutputDir GetEnv("PDF_IMG_OUTPUT_DIR")
#define MyOutputBase GetEnv("PDF_IMG_OUTPUT_BASE")
#define MyIconFile GetEnv("PDF_IMG_ICON_FILE")

[Setup]
AppId={{7F722F22-F751-4559-A8F8-CC98313D957B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=PDF-IMG
DefaultDirName={autopf}\PDF-IMG Extractor
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBase}
SetupIconFile={#MyIconFile}
UninstallDisplayIcon={app}\{#MyBuildName}.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyBuildName}.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyBuildName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyBuildName}.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
