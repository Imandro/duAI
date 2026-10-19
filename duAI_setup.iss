; duAI Setup Script para Inno Setup
; Compilar con: ISCC duAI_setup.iss

#define MyAppName "duAI"
#define MyAppPublisher "Imandro"
#define MyAppURL "https://github.com/Imandro/duAI"
#define MyAppExeName "duAI.exe"
#define MyAppVersion "2.0.0"

[Setup]
AppId={{8C4F123A-1234-1234-1234-123456789ABC}}
AppName={#MyAppName}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
InfoBeforeFile=README.md
OutputDir=installer
OutputBaseFilename=duAI-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
Uninstallable=yes
ChangesEnvironment=no
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=yes
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Ejecutar duAI al iniciar sesion"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\duAI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config\*"; DestDir: "{app}\config"; Flags: ignoresubdirignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoresubdirignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Nota: no crear tarea de autostart automaticamente por seguridad.
    // El usuario puede activarla desde Ajustes > Programador.
  end;
end;

function UninstallNeeded: Boolean;
begin
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = ssUninstall then
  begin
    // Limpiar datos de usuario en %LOCALAPPDATA%\duAI
    // Nota: Inno Setup no puede borrar facilmente rutas de variables de entorno
    // sin llamar a un script externo. Se deja a cargo del usuario o de un script
    // de desinstalacion adicional si se requiere limpieza profunda.
  end;
end;
