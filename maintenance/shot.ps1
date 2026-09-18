# Screenshot the Firefox main window via GDI (CopyFromScreen).
# Usage: .\shot.ps1 [-OutFile <png>]
#
# CAVEAT: this is an OS-level capture. On scaled displays (e.g. 200%) the
# DPI-unaware PowerShell process gets virtualised coordinates, so pixel
# positions in the PNG do NOT match CSS px, and the window frame/DWM may
# introduce artifacts (stray edge bands). For chrome-UI ground truth use
# drawwindow.py instead, which renders via Firefox's own compositor.
param(
    [string]$OutFile = (Join-Path $PSScriptRoot "shot.png")
)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$proc = Get-Process firefox -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { Write-Output "NO_WINDOW"; exit 1 }
[Win32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 300
$r = New-Object Win32+RECT
[Win32]::GetWindowRect($proc.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
if ($w -le 0 -or $h -le 0) { Write-Output "BAD_RECT"; exit 1 }
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size($w, $h)))
$g.Dispose()
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "SAVED $OutFile RECT=$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)"
