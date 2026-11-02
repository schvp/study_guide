# Проверка проекта

## Быстрая проверка

Перед небольшим коммитом запустите проверки синтаксиса Python и структуры учебных материалов:

```bash
python check_project.py --quick
```

Команда компилирует Python-модули и проверяет JSON-описания курсов, ссылки на Markdown-файлы и порядок глав.

## Полная проверка

Перед отправкой ветки выполните полный набор проверок:

```bash
python check_project.py
```

Помимо быстрых проверок команда запускает все модульные и интеграционные тесты из каталога `tests`.
Каждый тест приложения использует отдельную временную SQLite-базу и не изменяет рабочую базу
`instance/study_guide.sqlite3`.

## Выборочный запуск тестов

Для проверки одного модуля используйте стандартный `unittest`:

```bash
python -m unittest tests.test_health
python -m unittest tests.test_auth
```

Один тест можно запустить по полному имени:

```bash
python -m unittest tests.test_health.HealthEndpointTests.test_health_reports_database_status
```

## Непрерывная интеграция

GitHub Actions повторяет основные проверки для каждого push и pull request в `main`:

1. устанавливает зависимости из `requirements.txt`;
2. проверяет синтаксис Python-файлов;
3. валидирует учебные материалы;
4. запускает весь набор тестов.

Pull request следует объединять только после успешного завершения workflow `Tests`.
