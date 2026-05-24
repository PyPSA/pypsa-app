Unicode true

####
## pypsa-desktop NSIS installer
##
## Build workflow (on a Windows machine with NSIS and makensis in PATH):
##
##   Step 1 — populate wails_tools.nsh and build the Wails binary:
##     cd desktop
##     wails build --target windows/amd64 --nsis
##
##   Step 2 — place supporting files next to this script's parent directory:
##     desktop\build\windows\uv.exe              (download from https://github.com/astral-sh/uv/releases)
##     desktop\build\windows\wheels\pypsa-app\   (*.whl files built with `uv build`)
##     desktop\build\windows\wheels\snakedispatch\ (*.whl files built with `uv build`)
##
##   Step 3 — run makensis from this directory:
##     makensis -DARG_WAILS_AMD64_BINARY=..\..\bin\pypsa-desktop.exe project.nsi
##
## Output: desktop\build\bin\pypsa-desktop-setup-v<VERSION>-amd64.exe
####

; Pin product metadata here so wails_tools.nsh !ifndef guards leave them alone.
; Update INFO_PRODUCTVERSION when cutting a new release.
!define INFO_PROJECTNAME    "pypsa-desktop"
!define INFO_COMPANYNAME    "mikoding"
!define INFO_PRODUCTNAME    "pypsa-desktop"
!define INFO_PRODUCTVERSION "0.1.0"
!define INFO_COPYRIGHT      "Copyright 2025 mikoding"

!include "wails_tools.nsh"
!include "LogicLib.nsh"

; Version resource (must be 4-part integer, e.g. 0.1.0.0)
VIProductVersion "${INFO_PRODUCTVERSION}.0"
VIFileVersion    "${INFO_PRODUCTVERSION}.0"

VIAddVersionKey "CompanyName"     "${INFO_COMPANYNAME}"
VIAddVersionKey "FileDescription" "${INFO_PRODUCTNAME} Installer"
VIAddVersionKey "ProductVersion"  "${INFO_PRODUCTVERSION}"
VIAddVersionKey "FileVersion"     "${INFO_PRODUCTVERSION}"
VIAddVersionKey "LegalCopyright"  "${INFO_COPYRIGHT}"
VIAddVersionKey "ProductName"     "${INFO_PRODUCTNAME}"

ManifestDPIAware true

!include "MUI.nsh"

!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; Code-signing hooks — uncomment and fill in cert path/password for release builds.
; Requires signtool.exe (Windows SDK) in PATH.
;!finalize       'signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p "${CERT_PASSWORD}" "%1"'
;!uninstfinalize 'signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p "${CERT_PASSWORD}" "%1"'

Name "${INFO_PRODUCTNAME}"
OutFile "..\..\bin\${INFO_PROJECTNAME}-setup-v${INFO_PRODUCTVERSION}-${ARCH}.exe"
InstallDir "$PROGRAMFILES64\${INFO_PROJECTNAME}"
ShowInstDetails show

; Global scratch registers
Var MissingPrereqs
Var ScratchStr

Function .onInit
    !insertmacro wails.checkArchitecture
FunctionEnd

; ── Main install section ─────────────────────────────────────────────────────

Section "pypsa-desktop" SEC_MAIN
    !insertmacro wails.setShellContext

    ; Install WebView2 runtime if not already present (online bootstrapper).
    !insertmacro wails.webview2runtime

    SetOutPath $INSTDIR

    ; Install the Wails binary (arch-specific, selected by wails.files macro).
    !insertmacro wails.files

    ; Bundle uv binary — used by the app for offline Python environment creation.
    ; Source: ..\uv.exe  (desktop\build\windows\uv.exe)
    File "/oname=uv.exe" "..\uv.exe"

    ; Bundle pre-built Python wheels for offline first-launch setup.
    ; Placed in subdirs so setup.go's --find-links can locate them by venv name.
    SetOutPath "$INSTDIR\wheels\pypsa-app"
    File /r "..\wheels\pypsa-app\*"

    SetOutPath "$INSTDIR\wheels\snakedispatch"
    File /r "..\wheels\snakedispatch\*"

    SetOutPath $INSTDIR

    CreateShortcut "$SMPROGRAMS\${INFO_PRODUCTNAME}.lnk" "$INSTDIR\${PRODUCT_EXECUTABLE}"
    CreateShortCut "$DESKTOP\${INFO_PRODUCTNAME}.lnk"    "$INSTDIR\${PRODUCT_EXECUTABLE}"

    !insertmacro wails.associateFiles
    !insertmacro wails.associateCustomProtocols
    !insertmacro wails.writeUninstaller
SectionEnd

; ── Prerequisite check ───────────────────────────────────────────────────────
; Runs as a hidden section (name starts with "-") after SEC_MAIN.
; The app repeats this check at every startup, so this is a convenience warning.

Section "-PrerequisiteCheck" SEC_PREREQS
    StrCpy $MissingPrereqs ""

    nsExec::ExecToStack '"$WINDIR\System32\where.exe" git'
    Pop $0   ; exit code (0 = found)
    Pop $1   ; stdout (discard)
    ${If} $0 != 0
        StrCpy $ScratchStr "Git for Windows  (https://git-scm.com/download/win)$\n"
        StrCpy $MissingPrereqs "$MissingPrereqs$ScratchStr"
    ${EndIf}

    nsExec::ExecToStack '"$WINDIR\System32\where.exe" pixi'
    Pop $0
    Pop $1
    ${If} $0 != 0
        StrCpy $ScratchStr "Pixi  (winget install prefix-dev.pixi)$\n"
        StrCpy $MissingPrereqs "$MissingPrereqs$ScratchStr"
    ${EndIf}

    ${If} $MissingPrereqs != ""
        StrCpy $ScratchStr "$MissingPrereqs"
        MessageBox MB_OK|MB_ICONINFORMATION \
            "pypsa-desktop installed successfully.$\n$\n\
The following prerequisites were not detected on this machine.$\n\
Snakemake workflow execution requires them:$\n$\n\
$ScratchStr$\nInstall them and restart pypsa-desktop."
    ${EndIf}
SectionEnd

; ── Uninstaller ──────────────────────────────────────────────────────────────

Section "uninstall"
    !insertmacro wails.setShellContext

    ; Remove program files: exe, uv.exe, bundled wheels, and the uninstaller.
    ; User data at %APPDATA%\pypsa-desktop\ (SQLite DB, Python venvs, logs, workflow
    ; results) is deliberately NOT removed so the user's work is preserved.
    RMDir /r $INSTDIR

    Delete "$SMPROGRAMS\${INFO_PRODUCTNAME}.lnk"
    Delete "$DESKTOP\${INFO_PRODUCTNAME}.lnk"

    !insertmacro wails.unassociateFiles
    !insertmacro wails.unassociateCustomProtocols
    !insertmacro wails.deleteUninstaller
SectionEnd
