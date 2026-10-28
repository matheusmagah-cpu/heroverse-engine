# ChatGPT images through the owner's ChatGPT desktop app (owner's PC)

Owner, 2026-10-28: still images from ChatGPT in his own account, with our approved character stills as references,
through "o programa que tem no meu computador": the ChatGPT desktop app, already signed in, on device "Matheus",
driven through Desktop Commander. chatgpt.com in a browser stops at Cloudflare's check (which we never work around),
so the browser route was dropped. Gemini's free key cannot make images (limit 0, `evidence/gemini-image/`).

## Files (`C:\HeroVerse\chatgpt-runner`, venv with pywinauto and mcp)
- `app_driver.py`: the driver (Windows UI Automation). `status`, `job JOB.json`, `image --prompt --ref --out`.
- `chatgpt_core.py`: the rules (job checks, ledger, 3 min apart, 30 a day, limit/verification texts, record).
- `bridge.py`: `job` (cloud side: builds the job from a still record and approved refs by URL + sha256) and `push`
  (PC side: the candidate to branch `claude/chatgpt-image-<id>` through `gh`, once the owner ran `gh auth login`).
- `mcp_server.py`: stdio MCP with `chatgpt_app_status` and `chatgpt_app_image`.
- `deploy.py <commit>`: install/update from the public repository.

## How the driver works
The app is Electron: it shows its controls to UI Automation only while Windows' screen-reader flag is on, so the
driver turns that OS flag on for the run and puts it back (a killed run's value is kept in `screenreader.was` and
restored by the next run). It reads only the main area (x > 350) of a NEW chat, never the sidebar with the owner's
chats. Like a person: the mouse glides to each control and clicks, with pauses of seconds between steps:
"Novo chat", mode "Chat", "+" > "Criar imagem", "+" > "Adicionar fotos e arquivos" (the app's own file dialog, the
reference files' paths), the prompt pasted, "Enviar". It waits for a large image in the new chat with "Enviar" back
(no stop button), opens the image and uses the app's own download button; the file is picked up from Downloads.
The record: prompt, refs by sha256, times, sha256, size, `is_16_9`, OpenAI's ownership terms and the automation note.

While it runs, the ChatGPT app is in front and busy and the clipboard is replaced: nobody should use it then.
One request at a time, 3 min apart at least, 30 a day. A limit, error or verification text in the new chat stops it
(exit 5 or 4) for the owner to look at; nothing is solved or worked around. No credential is ever read.

## Bridge (cloud agents, Desktop Commander)
1. In the repository: `python3 migration/integrations/chatgpt-local/bridge.py job <still record> "<subject>"
   <approved ref records...> --ref-commit <full main sha>`.
2. `create_directory C:\HeroVerse\chatgpt-runner\jobs` (once), `write_file ...\jobs\<id>.json`, then `start_process`
   `C:\HeroVerse\chatgpt-runner\.venv\Scripts\python.exe C:\HeroVerse\chatgpt-runner\app_driver.py job
   C:\HeroVerse\chatgpt-runner\jobs\<id>.json` and `read_process_output` until `IMAGE_SAVED` or a stop line.
3. `read_file` the image (Desktop Commander shows it) and its record for Claude's still review; `bridge.py push <id>`
   brings it to the repository as a DRAFT candidate.

## Licence and account risk
OpenAI's Terms of Use (effective 2026-01-01): "you ... (b) own the Output. We hereby assign to you all our right,
title, and interest, if any, in and to Output". The same terms forbid extracting Output "automatically or
programmatically"; the driver runs in the owner's own app at his explicit request, so the account risk is his
(`licence.automation_note` in every record).
