# Future Cleanup Plan

Phases A+B completed 2026-01-03. The following items are deferred for later.

## D1. Split `launcher.py` into Modules (~2 hours)

The 2,220-line launcher would become:
```
launcher/
├── __init__.py
├── main.py              # Main window, tabs, entry point
├── dashboard_tab.py     # Dashboard panel
├── character_tab.py     # Character settings
├── llm_tab.py           # LLM settings
├── importer_dialog.py   # Chub import window
├── creator_dialog.py    # Character creator window
└── conversation_window.py
```

## D2. Split `app.js` into Modules (~1 hour)

The 1,541-line frontend would become:
```
web/js/
├── app.js           # Main init, event listeners
├── chat.js          # Message rendering, sending
├── media.js         # Image/video generation
├── sceneQueue.js    # Story queue
├── settings.js      # Settings modal
└── lora.js          # LoRA management
```
Can use native ES modules (no build step needed).

## D4. Move Characters to JSON (~1 hour)

Convert 90KB `characters.py` into `characters.json`. Requires updating:
- `characters.py` → JSON loader
- `launcher.py` → minor updates

## Recommended Order

D1 (biggest file) → D2 → D4 (lowest priority)
