# Telegram Userbot

## Команды

`.help` — список команд.

`.ocr [language]` — OCR изображения. По умолчанию используется `rus+eng`.

`.delete <count>` — удаляет сообщения пользователя из текущего чата или текущего топика. `-1` удаляет всю доступную историю пользователя до начала чата.

`.reboot` — перезапускает процесс userbot. Контейнер code runner при этом сохраняется, а запущенные программы восстанавливают мониторинг после старта.

## Code runner

Поддерживаются: Python, Node.js, C++, Java и Brainfuck.

Команды: `.python [filename]`, `.node [filename]`, `.cpp [filename]`, `.java [filename]`, `.brainfuck [filename]`, `.run <filename>`, `.stop <filename>`, `.debug [on|off|toggle]`, `.exec <command>`, `.reset`.

Формат команды с кодом:

    .python test
    ```python
    print("Hello")
    ```

При отсутствии имени файла создаётся `app.ext`, затем `app-2.ext`, `app-3.ext` и так далее. Если расширение указано в имени, оно нормализуется под выбранный язык.

Если блока кода нет, но команда является reply, первый fenced code block берётся из сообщения, на которое сделан reply.

Каждый чат и каждый Telegram-топик имеют отдельную рабочую область в `storage/workspaces`. Один Docker-контейнер обслуживает все рабочие области.

Программа запускается в отдельной process group внутри контейнера. Stdout и stderr попадают в log-файл, который userbot читает и отправляет в текущий чат и текущий топик. При `.debug off` живые сообщения отключаются, а накопленный вывод отправляется после завершения программы.

Для остановки используется `.stop <filename>`, для повторного запуска уже существующего файла — `.run <filename>`. `.reset` удаляет контейнер и создаёт новый из подготовленного image, не удаляя исходные файлы рабочих областей.

## OCR

`.ocr`, `.ocr ru`, `.ocr eng`, `.ocr ru+eng`, `.ocr ru/eng` и `.ocr ру/англ` поддерживаются как варианты выбора языка. OCR использует несколько вариантов preprocessing и несколько режимов Tesseract, после чего выбирает результат с наибольшей оценкой confidence.

## Установка

```bash
pip install -r requirements.txt
python main.py
```

Для code runner Docker daemon должен быть доступен пользователю, под которым запущен userbot. Если image ещё нет, он автоматически собирается из `docker/code-runner/Dockerfile`. Параметр `CODE_RUNNER_USER` можно задать явно как `UID:GID`; по умолчанию используется UID/GID текущего пользователя. Для OCR на VPS должны быть установлены Tesseract и языковые пакеты `eng`/`rus`, например `tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus`.

## Проверка

```bash
python -m compileall -q bot main.py docker/code-runner/brainfuck
pytest -q
```
