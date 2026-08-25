# PII Log Cleaner

Offline Windows desktop app for analyzing log/text files before generating separate de-identified outputs.

## What is implemented

- PySide6 single-screen UI matching the supplied layout: file/folder selection, 11 detection toggles, masking choices, execution summary, history, and a three-column preview.
- Regex detection for RRN-form values, Korean phone numbers, email, IPv4, URL, date, account key-values, and API-key/password key-values; offset-based overlap resolution and replacement.
- Optional bundled `schift-ko-pii-v6` local model adapter. The app sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` before model imports; it never downloads at runtime.
- Streaming analysis/de-identification, separate `_deid` outputs, optional original backups, CSV aggregate report, and PII-minimizing local SQLite history.

## Windows build: one installer EXE

Prerequisites on the Windows build machine:

1. 64-bit Python 3.11 (or another supported 3.10+ interpreter) and Inno Setup 6.
2. A licensed local snapshot of `schift-ko-pii-v6`, including `config.json`, `tokenizer.json`, `tokenizer_config.json`, `model.safetensors`, `modeling_lfm2_bidirectional.py`, and `LICENSE*`.

Run from PowerShell:

```powershell
.\build-windows.ps1 -ModelPath C:\secure-build-assets\schift-ko-pii-v6
```

The script creates `dist\PII-Log-Cleaner-Setup.exe`. It deliberately uses PyInstaller `onedir` internally—so the 136 MB model is installed normally rather than unpacked to a temporary directory every launch—then Inno Setup produces the single installer the user receives.

## Local core checks

```bash
python3 -m unittest discover -s tests -v
```

`--demo --allow-regex-only` are development-only flags for previewing the UI without a bundled model. They are not used by the Windows installer path.
