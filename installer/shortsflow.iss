; Inno Setup script - a small installer that downloads and sets up everything on the user's machine.
; Build:  iscc /DAppVersion=0.1.2 installer\shortsflow.iss      (output: installer\output\ShortsFlow-Setup-<version>.exe)
; No admin rights needed. The big downloads (Python, torch, Node) happen on first install via Install-ShortsFlow.ps1,
; so nothing third-party (Remotion, torch) is redistributed in this file.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B3F1C0A4-5C0D-4E57-9B0B-3B7E8C1A6F21}
AppName=ShortsFlow
AppVersion={#AppVersion}
AppPublisher=ShortsFlow
AppPublisherURL=https://github.com/ghost1412/shorts-generator
DefaultDirName={localappdata}\ShortsFlow
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=ShortsFlow-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=ShortsFlow
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Files]
Source: "Install-ShortsFlow.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "Uninstall-ShortsFlow.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\ShortsFlow"; Filename: "{app}\ShortsFlow.cmd"; WorkingDir: "{app}\workspace"
Name: "{autodesktop}\ShortsFlow"; Filename: "{app}\ShortsFlow.cmd"; WorkingDir: "{app}\workspace"

[Run]
Filename: "{app}\ShortsFlow.cmd"; Description: "Open ShortsFlow now"; Flags: postinstall nowait skipifsilent shellexec

; The user's workspace (videos, .env) is deliberately NOT removed on uninstall.
[UninstallDelete]
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\node"
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\cache"
Type: files; Name: "{app}\ShortsFlow.cmd"
Type: files; Name: "{app}\ShortsFlow Terminal.cmd"
Type: files; Name: "{app}\installed.txt"
Type: files; Name: "{app}\install.log"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Downloading and setting up ShortsFlow (this takes several minutes)...';
    if (not Exec('powershell.exe',
          '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\installer\Install-ShortsFlow.ps1') +
          '" -InstallDir "' + ExpandConstant('{app}') + '" -NoShortcuts',
          '', SW_SHOW, ewWaitUntilTerminated, ResultCode)) or (ResultCode <> 0) then
      MsgBox('Setup could not finish downloading everything.' + #13#10 +
             'Check your internet connection, then run this installer again (it resumes where it stopped).' + #13#10 +
             'Details: ' + ExpandConstant('{app}\install.log'), mbError, MB_OK);
  end;
end;
