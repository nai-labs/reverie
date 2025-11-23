# Terminal Customization Guide (Final Setup)

Your terminal is now customized with **Oh My Posh** and **lsd**.

## Configuration Details

### 1. Theme
*   **File**: `exact_match.omp.json` (located in your project folder).
*   **Style**: Replicates the "Powerline" look with specific blue/green/red colors.
*   **Segments**:
    *   **Left**: Path (folder icon), Git Branch, Python Venv.
    *   **Right**: Status (Error/Success), Execution Time, Current Time.

### 2. Icons (lsd)
*   **Executable**: `lsd.exe` (located in `C:\AI\discord-dreams\lsd.exe`).
*   **Aliases**:
    *   `ls`: Runs `lsd` with icons, headers, and grouped directories.
    *   `ll`: Shortcut for `ls`.
    *   `la`: Shortcut for `ls -a` (shows hidden files).

### 3. Font
*   **Font**: `MesloLGS NF` (must be installed and selected in VS Code settings).

## How it loads
Your PowerShell profile (`$PROFILE`) has been updated to:
1.  Load the `exact_match.omp.json` theme.
2.  Define the `ls` function to use the local `lsd.exe`.

> **Note**: If you move the `discord-dreams` folder, the `ls` command will break because it points to the `lsd.exe` inside this folder. You would need to update your profile path.
