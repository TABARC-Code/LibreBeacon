; Per-user Windows installer. No admin rights and no start-on-boot surprises.
; The app doesn't monitor while closed. Make that clear, even if it's awkward.
Unicode True
!include "MUI2.nsh"

!define APP_NAME "LibreBeacon"
!define APP_VERSION "4.3.0"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\LibreBeacon"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\dist\LibreBeacon-Setup-v${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\LibreBeacon"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "LibreBeacon" Main
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  ; NSIS resolves File and OutFile paths from this script folder.
  File "..\dist\LibreBeacon.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\LibreBeacon"
  CreateShortcut "$SMPROGRAMS\LibreBeacon\LibreBeacon.lnk" "$INSTDIR\LibreBeacon.exe"
  CreateShortcut "$SMPROGRAMS\LibreBeacon\Uninstall LibreBeacon.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "LibreBeacon ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\LibreBeacon.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '$"$INSTDIR\Uninstall.exe$"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '$"$INSTDIR\Uninstall.exe$" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$SMPROGRAMS\LibreBeacon\LibreBeacon.lnk"
  Delete "$SMPROGRAMS\LibreBeacon\Uninstall LibreBeacon.lnk"
  RMDir "$SMPROGRAMS\LibreBeacon"
  Delete "$INSTDIR\LibreBeacon.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  ; Keep settings and the Windows credential-store entry. It'd be rotten to
  ; remove a person's configuration without asking; document manual removal.
SectionEnd
