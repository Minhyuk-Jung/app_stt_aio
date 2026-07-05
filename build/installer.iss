; C16 Inno Setup script (plan §6.2). Requires PyInstaller output at dist\STT-AIO\.
; Models are NOT bundled — users download via C18 ModelManager / C21 Onboarding.

#define MyAppName "STT-AIO"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "STT-AIO"
#define MyAppExeName "STT-AIO.exe"
#define MyAppURL "https://github.com/stt-aio/stt-aio"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UsePreviousAppDir=yes
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=STT-AIO-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\STT-AIO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "SMARTSCREEN.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Messages]
korean.WelcomeLabel2=STT-AIO 음성 받아쓰기 앱을 설치합니다.%n%nWhisper 모델은 설치본에 포함되지 않습니다. 첫 실행 시 온보딩 또는 설정에서 다운로드하세요.%n%n이전 버전이 설치되어 있으면 같은 폴더에 덮어씁니다. 사용자 데이터(%APPDATA%\STT-AIO)는 유지됩니다.
english.WelcomeLabel2=This will install STT-AIO on your computer.%n%nWhisper models are not bundled. Download them on first run via onboarding or settings.%n%nIf a previous version is installed, files are upgraded in place. User data in %APPDATA%\STT-AIO is preserved.
