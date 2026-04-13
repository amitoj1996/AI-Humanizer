; AI Humanizer — Inno Setup installer script
;
; Builds a Windows installer that:
;   - Installs the PyInstaller onedir bundle to %LOCALAPPDATA%\Programs\AI Humanizer
;   - Registers Start Menu + Desktop shortcuts
;   - Detects WebView2 Evergreen Runtime — runs the bootstrapper if missing
;   - Detects Ollama — if not found, launches the official Ollama installer
;     (silent install is unreliable per ollama/ollama#7969, so we let the
;     user click through the real installer)
;   - No admin rights required (per-user install)
;
; Build: compile with Inno Setup 6.x on Windows.
;   iscc windows\installer.iss
;
; Output: windows\output\AIHumanizerSetup.exe

#define AppName "AI Humanizer"
#define AppVersion "2.0.0"
#define AppPublisher "AI Humanizer"
#define AppURL "https://github.com/amitoj1996/AI-Humanizer"
#define AppExeName "AI Humanizer.exe"

[Setup]
AppId={{5B4E6A2A-8A1D-4C5F-9E3C-0C7F8D2E1F3A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=output
OutputBaseFilename=AIHumanizerSetup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
DisableProgramGroupPage=yes
#ifexist "app.ico"
SetupIconFile=app.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller onedir bundle
Source: "..\dist\AI Humanizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Bundled WebView2 bootstrapper — tiny, runs conditionally at install time
Source: "bootstrap\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not WebView2Installed

; Bundled Ollama installer — downloaded into bootstrap/ before iscc runs
Source: "bootstrap\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not OllamaInstalled

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Install WebView2 runtime if missing (interactive — fast, rarely hit on Win11)
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; Check: not WebView2Installed; StatusMsg: "Installing Microsoft Edge WebView2 runtime..."; Flags: waituntilterminated

; Install Ollama if missing.  We run it interactively — Ollama's silent install
; is unreliable (see ollama/ollama#7969).  The user clicks Next a couple of
; times; they only do this once.
Filename: "{tmp}\OllamaSetup.exe"; Check: not OllamaInstalled; StatusMsg: "Installing Ollama..."; Flags: waituntilterminated

; Launch the app after install
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function WebView2Installed(): Boolean;
var
  Version: String;
begin
  // WebView2 Evergreen Runtime GUID.  Preinstalled on Win11 + recent Win10 updates.
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version)
    or RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
end;

function OllamaInstalled(): Boolean;
var
  OllamaPath: String;
begin
  // Ollama installs to %LOCALAPPDATA%\Programs\Ollama and adds itself to PATH.
  OllamaPath := ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe');
  Result := FileExists(OllamaPath);
end;
