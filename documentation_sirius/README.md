# Документационный портал

Исходники портала «Система расписания для Университета „Сириус“».

## Сборка HTML

```bash
PYTHONPATH=../tools/.sphinx-deps \
  /Users/root1/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m sphinx -W --keep-going -b html source build/html
```

Перед сборкой обновите ER-схемы и словарь данных:

```bash
/Users/root1/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  ../tools/generate_er_diagrams.py

/Users/root1/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  ../tools/generate_sphinx_database_docs.py
```

Откройте `build/html/index.html` в браузере или опубликуйте содержимое папки
`build/html` на внутреннем веб-сервере.
