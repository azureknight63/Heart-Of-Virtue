---
applyTo: '**'
description: 'description'
---
When writing scripts or commands in PowerShell, it's important to ensure compatibility across different versions of PowerShell and various operating systems. Here are some guidelines to help you achieve this:
- Use Cmdlets: Prefer using built-in cmdlets over external commands or scripts, as they are more likely to be compatible across different environments.
- Avoid Deprecated Features: Stay updated with the latest PowerShell documentation to avoid using features that may be deprecated in future versions.
- Avoid using invalid operators such as `&`, `&&` and `||` for command chaining. Instead, use `;` to separate commands.