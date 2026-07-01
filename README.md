# Telegram Bot (Mops-Farmila)

## Quick Deploy (Railway)

1. Push this folder to GitHub.
2. Create a new Railway project from the GitHub repo.
3. In Railway Variables, add:
   - `BOT_TOKEN` = your Telegram bot token
   - `OPENAI_API_KEY` = optional, enables full AI text/photo solving
   - `OPENAI_MODEL` = optional, default `gpt-4o-mini`
4. Railway will run `python bot.py` automatically.

`OPENAI_API_KEY` is not required for deploy. Without it the bot still starts and uses local fallback commands: calculator, equations, local photo analysis, study helper, recipe scaling, tech cards, nutrition estimates, summaries, mini-translation, notes, reminders and games.

For 24/7 work use Railway as a worker service. The included `Procfile` is:

```Procfile
worker: python bot.py
```

To keep JSON data after redeploys, add a Railway Volume or set `DATA_DIR`.

## Local Run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Set env variable:
   - Windows PowerShell: `$env:BOT_TOKEN="YOUR_TOKEN"`
3. Run:
   - `python bot.py`

## Files for deploy

- `Procfile` -> `worker: python bot.py`
- `railway.json` -> Railway start/restart settings
- `site/index.html` -> standalone command website

## Notes

- By default bot data (`*.json`) is saved near `bot.py`.
- If `DATA_DIR` or `RAILWAY_VOLUME_MOUNT_PATH` is set, data is saved there.
- AI/photo commands: `/ai`, `/ask`, `/solve`, `/analyze`, `/vision`, `/photo`, `/ocr`, `/summary`, `/translate`.
- Study commands: `/study`, `/math`, `/biology`, `/informatics`, `/food`, `/techcard`, `/scale_recipe`, `/proportion`, `/nutrition`, `/units`.
- Ultra commands: `/calc`, `/roll`, `/choose`, `/password`, `/remind`, `/note_add`, `/notes`, `/truth`, `/dare`, `/slots`, `/ship`, `/rate`, `/bomb`.
- Command website: open `site/index.html` in a browser or publish it with GitHub Pages.
