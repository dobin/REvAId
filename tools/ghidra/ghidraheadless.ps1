# GhidraMCP headless server launcher script for Windows PowerShell.
$ErrorActionPreference = "Stop"

# Configure the following variables to match your environment before running this script.

# Ghidra Installation directory (contains GhidraRun.bat, GhidraMCPHeadlessServer.class, etc.)
$GhidraInstall = "C:\Tools\ghidra_12.1.2_PUBLIC"

# Ghidra-mcp build output directory (git clone of https://github.com/bethington/ghidra-mcp and built)
$McpJar        = "C:\Tools\ghidra-mcp\target\GhidraMCP-*.jar"

# Ghidra project directory and name (contains the .gpr file)
$ProjectDir    = "C:\Data\ghidra\Defender"

# Ghidra project file path and program path (relative to project root)
$ProjectName   = "devrev-claude"
$ProjectFile   = Join-Path $ProjectDir "$ProjectName.gpr"

# Ghidra program path (relative to project root); must be a file, not a directory.
$ProgramPath   = "/mpengine.dll"

# Project owner recorded in the .gpr; a mismatch makes openProject() fail.
$GhidraUser    = "dobin"

# Java executable path; must be a JDK, not a JRE.
$JavaExe = "C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\java.exe"
$JavaExe = (Get-Item $JavaExe).FullName

#####
# Code follows, no changes needed below this line.

if (-not (Test-Path -LiteralPath $ProjectFile)) {
    throw "Ghidra project not found: $ProjectFile"
}

$jars = @(
    (Resolve-Path $McpJar | Select-Object -First 1).Path
)
$jars += (Get-ChildItem "$GhidraInstall\Ghidra\Framework\*\lib\*.jar").FullName
$jars += (Get-ChildItem "$GhidraInstall\Ghidra\Features\*\lib\*.jar").FullName
$jars += (Get-ChildItem "$GhidraInstall\Ghidra\Processors\*\lib\*.jar").FullName

$ClassPath = $jars -join ";"

Write-Host "Starting GhidraMCP headless server with pre-loaded program..."
Write-Host "Project: $ProjectFile"
Write-Host "Program: $ProgramPath"
Write-Host "Port:    8089"

# Note: --bind 127.0.0.1 is required unless GHIDRA_MCP_AUTH_TOKEN is set;
# startServer() refuses a non-loopback bind without a token.
& $JavaExe `
    "-Xmx4g" `
    "-XX:+UseG1GC" `
    "-Duser.name=$GhidraUser" `
    "-Dghidra.home=$GhidraInstall" `
    "-Dapplication.name=GhidraMCP" `
    "-classpath" $ClassPath `
    "com.xebyte.headless.GhidraMCPHeadlessServer" `
    "--bind" "127.0.0.1" `
    "--port" "8089" `
    "--project" $ProjectFile `
    "--program" $ProgramPath