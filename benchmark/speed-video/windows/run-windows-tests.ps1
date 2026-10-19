#Requires -Version 5.1
<#
.SYNOPSIS
    Parula speed test on Windows: run once, it does everything else on its own.

.DESCRIPTION
    Fetches what it needs into its own folder (portable Python, ffmpeg, the test scripts; Parula when it isn't
    installed), checks the prerequisites, then runs the whole test session: Parula (JMAP), Outlook (classic) and the
    new Outlook, one after another, 1 warm-up and 5 measured runs each, every run a new account setup, recorded
    from the screen. The result is one folder (and a zip of it) with all recordings and measurements.
    Needs no administrator rights. Everything it changes on this computer is undone at the end, also after an error
    or Ctrl+C.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\run-windows-tests.ps1 -Server mail.example.org -Email test@example.org
    (asks for the password without showing it)

.PARAMETER CodeRef
    The commit (or branch) of -CodeRepo whose test scripts it fetches; the default is the commit this script was
    released with, so the script and the scripts it runs always belong together.
#>
[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingWriteHost', '',
    Justification = 'Console messages for the person who runs the test')]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword', 'Password',
    Justification = 'Requested as a plain parameter; it goes only into the child process environment, never to a file')]
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Password,
    [string]$Root = '',
    [string]$CodeRepo = 'benb-creator/mustang',
    [string]$CodeRef = 'da4eb4108aaedb0462b696b1e713f61d6996179a',
    [switch]$CheckOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Pins = @{
    Python = @{
        Version = '3.13.16'
        Url     = 'https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip'
        Sha256  = '97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
    }
    Wheels = @(
        @{ Name = 'numpy-2.5.4-cp313-cp313-win_amd64.whl'
           Url = 'https://files.pythonhosted.org/packages/90/8c/140a40398a66b4471211be1affdb6ed24c486d581bd28d07b7f2fcb69540/numpy-2.5.4-cp313-cp313-win_amd64.whl'
           Sha256 = '8b4d2fd2d34e5f8c9235ee787de5631a37a28402b15cb80814df973d2be54129' },
        @{ Name = 'pillow-13.0.0-cp313-cp313-win_amd64.whl'
           Url = 'https://files.pythonhosted.org/packages/d7/ed/1b16fb66a37e1b9e41370b93b2c614c7da761a5b2a41dc333f7af4639962/pillow-13.0.0-cp313-cp313-win_amd64.whl'
           Sha256 = '9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42' },
        @{ Name = 'pyyaml-6.0.3-cp313-cp313-win_amd64.whl'
           Url = 'https://files.pythonhosted.org/packages/97/c9/39d5b874e8b28845e4ec2202b5da735d0199dbe5b8fb85f91398814a9a46/pyyaml-6.0.3-cp313-cp313-win_amd64.whl'
           Sha256 = '79005a0d97d5ddabfeeea4cf676af11e647e41d81c9a7722a193022accdb6b7c' },
        @{ Name = 'comtypes-1.4.17-py3-none-any.whl'
           Url = 'https://files.pythonhosted.org/packages/89/9c/d0bc1fb69ad22a04bdc01dd9b5613a2ebc4d02ba1ec24b02127dc93791ba/comtypes-1.4.17-py3-none-any.whl'
           Sha256 = '4e0a221dde2c589b82977bed802efd71cd5eb67a380347b732e02735e597f586' },
        @{ Name = 'websocket_client-1.9.2-py3-none-any.whl'
           Url = 'https://files.pythonhosted.org/packages/d5/d2/cc4dc1271e464942db7ee278baae2daa99ee77cb2af744025c04da585a3e/websocket_client-1.9.2-py3-none-any.whl'
           Sha256 = 'e1a673830a9c7bfa47b1cd3d5e4178f4c9651d80a4eab02c9c23a1c3ec6250ce' }
    )
    FFmpeg = @{
        Version = '8.1.2 (gyan.dev essentials)'
        Url     = 'https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/ffmpeg-8.1.2-essentials_build.zip'
        Sha256  = 'db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec'
        Folder  = 'ffmpeg-8.1.2-essentials_build'
    }
    Parula = @{
        Version = '0.9.39'
        Url     = 'https://github.com/mustang-im/mustang/releases/download/v0.9.39/parula-0.9.39-setup.exe'
        Sha256  = '6c14f20c4edd1faf715150b05a7089ed094aa7fd6ebec3a235bbf0d4134bbc48'
    }
}

if (-not $Root) { $Root = Join-Path (Get-Location).Path 'parula-speed-test' }
$Root = [IO.Path]::GetFullPath($Root)
$Tools = Join-Path $Root 'tools'
$StateDir = Join-Path $Root 'state'
New-Item -ItemType Directory -Force -Path $Tools, $StateDir | Out-Null
$LogFile = Join-Path $StateDir 'bootstrap.log'

function Write-Step([string]$Message) {
    $line = '{0:HH:mm:ss} {1}' -f (Get-Date), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Get-PinnedFile([string]$Url, [string]$Sha256, [string]$Target) {
    if ((Test-Path -LiteralPath $Target) -and ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $Sha256)) {
        return $Target
    }
    Write-Step "  downloading $Url"
    $partial = "$Target.partial"
    Invoke-WebRequest -Uri $Url -OutFile $partial -UseBasicParsing
    $actual = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash
    if ($actual -ne $Sha256) {
        Remove-Item -LiteralPath $partial -Force
        throw "SHA-256 of $Url is $actual, expected $Sha256; the download is not the pinned file"
    }
    Move-Item -LiteralPath $partial -Destination $Target -Force
    return $Target
}

function Expand-ZipTo([string]$Zip, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
    [IO.Compression.ZipFile]::ExtractToDirectory($Zip, $Destination)
}

function ConvertFrom-SecureText([Security.SecureString]$Secure) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

Write-Step "Parula speed test on Windows: folder $Root"

$os = [Environment]::OSVersion.Version
if ($os.Major -lt 10 -or $os.Build -lt 17763 -or -not [Environment]::Is64BitOperatingSystem) {
    throw "This test needs 64-bit Windows 10 (version 1809 or later) or Windows 11; this is $os"
}
$freeGb = [math]::Floor((Get-PSDrive -Name ([IO.Path]::GetPathRoot($Root).Substring(0, 1))).Free / 1GB)
if ($freeGb -lt 2) { throw "Only $freeGb GB free on the drive of $Root; the tools alone need 2 GB" }

# The test scripts: this checkout, or the pinned commit of the repository
$checkout = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $checkout 'bench.py')) {
    $Code = $checkout
    $CodeInfo = @{ source = 'local'; path = $Code }
    Write-Step "test scripts: $Code"
} else {
    $commit = (Invoke-RestMethod -Uri "https://api.github.com/repos/$CodeRepo/commits/$CodeRef" -UseBasicParsing).sha
    $Code = Join-Path $Tools "code-$($commit.Substring(0, 12))"
    if (-not (Test-Path -LiteralPath (Join-Path $Code 'bench.py'))) {
        Write-Step "fetching the test scripts of $CodeRepo $CodeRef ($commit)"
        $partialCode = "$Code.partial"
        if (Test-Path -LiteralPath $partialCode) { Remove-Item -LiteralPath $partialCode -Recurse -Force }
        $tree = Invoke-RestMethod -Uri "https://api.github.com/repos/$CodeRepo/git/trees/$($commit)?recursive=1" -UseBasicParsing
        $prefix = 'benchmark/speed-video/'
        foreach ($entry in $tree.tree) {
            if ($entry.type -ne 'blob' -or -not $entry.path.StartsWith($prefix) -or $entry.path.StartsWith($prefix + 'tests/')) { continue }
            $target = Join-Path $partialCode ($entry.path.Substring($prefix.Length) -replace '/', '\')
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Invoke-WebRequest -Uri "https://raw.githubusercontent.com/$CodeRepo/$commit/$($entry.path)" -OutFile $target -UseBasicParsing
        }
        if (-not (Test-Path -LiteralPath (Join-Path $partialCode 'bench.py'))) {
            throw "The test scripts of $CodeRepo $commit have no benchmark/speed-video/bench.py"
        }
        Move-Item -LiteralPath $partialCode -Destination $Code
    }
    $CodeInfo = @{ source = 'github'; repo = $CodeRepo; ref = $CodeRef; commit = $commit; path = $Code }
}
$CodeInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StateDir 'code.json') -Encoding UTF8

# Portable Python with pinned packages (wheels unpacked into its site-packages; no pip, no installer)
$pythonDir = Join-Path $Tools "python-$($Pins.Python.Version)"
$python = Join-Path $pythonDir 'python.exe'
$sitePackages = Join-Path $pythonDir 'Lib\site-packages'
$downloads = Join-Path $Tools 'downloads'
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $pythonDir 'bench-ready.txt'))) {
    Write-Step "installing Python $($Pins.Python.Version) (portable)"
    $zip = Get-PinnedFile -Url $Pins.Python.Url -Sha256 $Pins.Python.Sha256 -Target (Join-Path $downloads 'python-embed.zip')
    Expand-ZipTo -Zip $zip -Destination $pythonDir
    New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
    $pth = Get-ChildItem -LiteralPath $pythonDir -Filter 'python*._pth' | Select-Object -First 1
    Set-Content -LiteralPath $pth.FullName -Encoding ASCII -Value @(
        ((Get-ChildItem -LiteralPath $pythonDir -Filter 'python3*.zip' | Select-Object -First 1).Name), '.',
        'Lib\site-packages', 'import site')
    foreach ($wheel in $Pins.Wheels) {
        $file = Get-PinnedFile -Url $wheel.Url -Sha256 $wheel.Sha256 -Target (Join-Path $downloads $wheel.Name)
        Write-Step "  package $($wheel.Name)"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($file)
        try {
            foreach ($item in $archive.Entries) {
                if (-not $item.Name) { continue }
                $target = Join-Path $sitePackages ($item.FullName -replace '/', '\')
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($item, $target, $true)
            }
        } finally { $archive.Dispose() }
    }
    Set-Content -LiteralPath (Join-Path $pythonDir 'bench-ready.txt') -Value (Get-Date -Format o)
}

# ffmpeg (Desktop Duplication capture "ddagrab", lossless libx264rgb)
$ffmpegDir = Join-Path $Tools $Pins.FFmpeg.Folder
$ffmpeg = Join-Path $ffmpegDir 'bin\ffmpeg.exe'
$ffprobe = Join-Path $ffmpegDir 'bin\ffprobe.exe'
if (-not (Test-Path -LiteralPath $ffmpeg)) {
    Write-Step "installing ffmpeg $($Pins.FFmpeg.Version)"
    $zip = Get-PinnedFile -Url $Pins.FFmpeg.Url -Sha256 $Pins.FFmpeg.Sha256 -Target (Join-Path $downloads 'ffmpeg.zip')
    Expand-ZipTo -Zip $zip -Destination (Join-Path $Tools 'ffmpeg-unpacked')
    Move-Item -LiteralPath (Join-Path $Tools "ffmpeg-unpacked\$($Pins.FFmpeg.Folder)") -Destination $ffmpegDir
    Remove-Item -LiteralPath (Join-Path $Tools 'ffmpeg-unpacked') -Recurse -Force
}

# Parula: the installed one, or the pinned public release, installed for this user only (silent, no admin)
$parulaCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\parula\Parula.exe'),
    (Join-Path $env:ProgramFiles 'Parula\Parula.exe'))
$uninstall = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
    Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName -like 'Parula*' -and $_.PSObject.Properties['InstallLocation'] -and $_.InstallLocation } |
    Select-Object -First 1
if ($uninstall) { $parulaCandidates = @((Join-Path $uninstall.InstallLocation 'Parula.exe')) + $parulaCandidates }
$parulaExe = $parulaCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$parulaInstalled = 'already installed'
if (-not $parulaExe) {
    Write-Step "installing Parula $($Pins.Parula.Version) for this Windows user"
    $setup = Get-PinnedFile -Url $Pins.Parula.Url -Sha256 $Pins.Parula.Sha256 -Target (Join-Path $downloads "parula-$($Pins.Parula.Version)-setup.exe")
    $process = Start-Process -FilePath $setup -ArgumentList '/S' -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "The Parula installer ended with exit code $($process.ExitCode)" }
    Start-Sleep -Seconds 3
    Get-Process -Name 'parula' -ErrorAction SilentlyContinue | Stop-Process -Force
    $parulaExe = $parulaCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $parulaExe) { throw "Parula was installed, but Parula.exe isn't in $($parulaCandidates -join ', ')" }
    $parulaInstalled = "installed $($Pins.Parula.Version) by this script"
}
@{ path = $parulaExe; how = $parulaInstalled; version = (Get-Item -LiteralPath $parulaExe).VersionInfo.ProductVersion } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StateDir 'parula.json') -Encoding UTF8
Write-Step "Parula: $parulaExe ($parulaInstalled)"

# Outlook (classic): where Office registered it
$outlookExe = ''
foreach ($key in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE') {
    $entry = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
    if ($entry -and $entry.PSObject.Properties['(default)'] -and (Test-Path -LiteralPath $entry.'(default)'.Trim('"'))) {
        $outlookExe = $entry.'(default)'.Trim('"')
        break
    }
}

$secureCopy = $null
if (-not $Password) {
    $secureCopy = Read-Host -AsSecureString "Password of $Email (not shown)"
    $Password = ConvertFrom-SecureText $secureCopy
}
$env:BENCH_PASSWORD = $Password
$Password = $null

$arguments = @('--root', $Root, '--server', $Server, '--email', $Email, '--ffmpeg', $ffmpeg, '--ffprobe', $ffprobe,
               '--parula-exe', $parulaExe, '--outlook-exe', $outlookExe)
$winbench = Join-Path $Code 'windows\winbench.py'
$exitCode = 1
try {
    if ($CheckOnly) {
        & $python $winbench check @arguments
        $exitCode = $LASTEXITCODE
    } else {
        Write-Step 'Starting the test session. It takes several hours; please do not use this computer until it ends.'
        & $python $winbench session @arguments
        $exitCode = $LASTEXITCODE
    }
} finally {
    & $python $winbench cleanup --root $Root | Out-Host
    Remove-Item -Path Env:BENCH_PASSWORD -ErrorAction SilentlyContinue
    if ($secureCopy) { $secureCopy.Dispose() }
    Write-Step "done (exit code $exitCode)"
}
exit $exitCode
