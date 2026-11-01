# SegVision Native App (default GUI)

Default desktop shell: React + Vite UI, Tauri 2 host, Python sidecar.

PySide6 remains available as `segvision-pyside6` / `segvision pyside6`.

The development Native App requests the official CPU MobileSAM backend. It validates
`models/local-evaluation.json`, the referenced local-evaluation authorization and
provenance records, and the checkpoint SHA-256 before deserialization. This local
runtime permission is not release or redistribution approval. A failed gate is shown
as a fake-backend setup blocker rather than being reported as MobileSAM.

## Launch

From the repository root, with `.venv` active:

```powershell
segvision-gui
# or
segvision gui
# or
npm --prefix apps/desktop-host run dev
```

## Tests

```powershell
python -m pytest tests/contract tests/integration/test_desktop_sidecar.py tests/desktop-e2e -q
Set-Location apps/desktop-ui; npm test
```
