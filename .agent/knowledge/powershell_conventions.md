# PowerShell Command Conventions

When working in this environment (Windows/PowerShell), always use PowerShell-native commands instead of Unix-based ones like `grep`.

## Search Commands
- Use `Select-String` instead of `grep`.
- Syntax: `Select-String -Path "path\to\file" -Pattern "pattern"`
- For recursive search: `Get-ChildItem -Recurse | Select-String -Pattern "pattern"` or `Select-String -Path "target\**\*.js" -Pattern "pattern"`

## Directory Listing
- Use `dir` or `ls` (aliases for `Get-ChildItem`).

## File Manipulation
- Use `type` or `cat` (aliases for `Get-Content`).
- Use `echo` (alias for `Write-Output`).
