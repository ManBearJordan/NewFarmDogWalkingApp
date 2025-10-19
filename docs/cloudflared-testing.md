# Testing Cloudflared Detection in start-nfdw.bat

This document describes how to test the cloudflared detection and graceful fallback functionality in the `start-nfdw.bat` script.

## Test Scenarios

### Scenario 1: Cloudflared Not Installed (Graceful Degradation)

**Expected Behavior**: The script should:
1. Start Waitress successfully on http://127.0.0.1:8000
2. Display a warning message indicating cloudflared was not found
3. Show installation instructions using winget
4. Continue running without cloudflared

**How to Test**:
1. Ensure cloudflared is not installed or in PATH
2. Run `start-nfdw.bat`
3. Verify the warning message appears
4. Verify Waitress is running on http://127.0.0.1:8000
5. Verify no cloudflared process is started

### Scenario 2: Cloudflared in PATH

**Expected Behavior**: The script should:
1. Find cloudflared using the `where` command
2. Start both Waitress and cloudflared
3. Display the cloudflared path being used

**How to Test**:
1. Install cloudflared using: `winget install --id Cloudflare.cloudflared -e`
2. Run `start-nfdw.bat`
3. Verify both services start
4. Check logs in `logs\cloudflared.out.log`

### Scenario 3: Cloudflared in Local Directory

**Expected Behavior**: The script should find cloudflared in `.\cloudflared\cloudflared.exe`

**How to Test**:
1. Create directory: `mkdir cloudflared`
2. Copy cloudflared.exe to `.\cloudflared\cloudflared.exe`
3. Run `start-nfdw.bat`
4. Verify it uses the local cloudflared

### Scenario 4: Cloudflared in Program Files

**Expected Behavior**: The script should find cloudflared in `%ProgramFiles%\Cloudflare\cloudflared\cloudflared.exe`

**How to Test**:
1. Install cloudflared to Program Files (standard installation)
2. Ensure it's not in PATH
3. Run `start-nfdw.bat`
4. Verify it finds and uses the Program Files installation

### Scenario 5: Custom Path via CLOUDFLARED_EXE

**Expected Behavior**: The script should respect the CLOUDFLARED_EXE environment variable

**How to Test**:
1. Set environment variable: `set CLOUDFLARED_EXE=C:\custom\path\cloudflared.exe`
2. Place cloudflared at that location
3. Run `start-nfdw.bat`
4. Verify it uses the custom path

## Verification Steps

After running the script, verify:
1. Check running processes: `tasklist | findstr /i "python cloudflared waitress"`
2. Check logs directory: `dir logs`
3. Verify Waitress is listening: Open http://127.0.0.1:8000 in browser
4. Check cloudflared logs: `type logs\cloudflared.out.log`

## Cleanup

To stop all services:
```bat
stop-nfdw.bat
```

Or manually:
```bat
taskkill /F /FI "WINDOWTITLE eq NFDW Waitress*"
taskkill /F /FI "WINDOWTITLE eq NFDW Cloudflare*"
```
