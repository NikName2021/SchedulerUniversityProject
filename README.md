# Система расписания для Университета «Сириус»

Веб-система для подготовки, автоматического формирования, проверки и публикации учебного расписания. Решение учитывает учебную нагрузку, доступность преподавателей и аудиторий, календарные ограничения, ручные фиксации и конфликты ресурсов.

## Возможности

- импорт учебной нагрузки из Excel, CSV и XLSX с объединением связанных групп в учебные потоки;
- ведение справочников дисциплин, видов занятий, корпусов, аудиторий и их оснащения;
- календарное планирование: учебные периоды, недели, праздники и правила доступности;
- автоматическое формирование расписания с помощью Google OR-Tools CP-SAT;
- ручная корректировка, фиксация занятий и проверка конфликтов до сохранения;
- асинхронные или переносимые локальные расчёты, загрузка результата,
  диагностика, версии, публикация и экспорт в Excel;
- локальный и production-контур на Docker Compose.

## Роли

| Роль | Зона ответственности |
| --- | --- |
| Оператор расписания | Загружает и проверяет данные, настраивает ограничения, запускает расчёты, корректирует и публикует расписание. |
| Технический администратор | Развёртывает и обновляет сервисы, применяет миграции, следит за health-check, журналами и очередью задач. |

Доступ к интерфейсу и рабочим API-маршрутам закрыт локальной авторизацией.
Пароли хранятся как Argon2id-хэши, сессии — на сервере, а браузер получает
только `HttpOnly` cookie. Роль сохраняется в учётной записи и отображается в
интерфейсе; детальное разграничение операций между администратором и оператором
остаётся следующим этапом.

## Архитектура

```text
React + Vite + TypeScript
          │ HTTP / REST
          ▼
FastAPI + SQLAlchemy + Pydantic
     ├──────────────► PostgreSQL — данные, версии и публикации
     ├──────────────► пакет .scheduler-task ──► локальный OR-Tools
     │                                           │
     │               пакет .scheduler-result ◄──┘
     └──────────────► Redis + Celery — опциональный серверный расчёт
```

### Алгоритм формирования расписания

Для каждого занятия и допустимого временного слота создаётся булева переменная: она показывает, назначено ли занятие в этот слот. До создания модели исключаются заведомо недопустимые варианты: праздники, недоступность преподавателя или группы, а также уже зафиксированные конфликтующие занятия.

CP-SAT соблюдает жёсткие ограничения: занятие не может занимать два слота одновременно, группа и преподаватель не могут вести две пары в одно время, фиксированные занятия сохраняются, а обязательные перерывы не нарушаются. Мягкие критерии — поздние пары, окна, предпочтения доступности и порядок «лекция → практика» — входят в целевую функцию с весами профиля правил. Если полное размещение невозможно, модель фиксирует дефицит и возвращает диагностические сообщения.

Независимые компоненты конфликтов рассчитываются отдельно и могут выполняться параллельно в Celery worker. Подбор аудиторий для уже размещённых занятий выполняется отдельной CP-SAT-моделью с учётом вместимости, типа и оснащения аудитории.

## Технологии

| Слой | Технологии |
| --- | --- |
| Клиент | React 19, TypeScript, Vite, Zustand, Tailwind CSS, Lucide React |
| API | Python 3.10+, FastAPI, Pydantic v2 |
| Данные | SQLAlchemy 2.0, Alembic, PostgreSQL; SQLite — для локальной разработки и тестов |
| Расчёт | Google OR-Tools CP-SAT |
| Фоновые задачи | Celery и Redis |
| Импорт и экспорт | Pandas, OpenPyXL |
| Развёртывание | Docker Compose, Nginx |

## Структура проекта

```text
src/app/                  backend: API, модели, миграции, сервисы и алгоритм
spa/                      React-приложение оператора расписания
documentation_sirius/     исходники и собранный HTML-портал документации
docs/                     технические документы по этапам разработки
deliverables/             итоговые поставляемые документы
tools/                    генераторы ER-схем и справочных материалов
docker-compose.yml        production-контур
```

## Запуск в Docker

По умолчанию запускается лёгкий контур: PostgreSQL, FastAPI и Nginx с
собранным React-приложением. Redis и Celery worker не запускаются, а расчёты
экспортируются для выполнения на рабочем компьютере.

```bash

python3 create_env.py
cp ./spa/.env.example ./spa/.env
docker compose up --build
```
Либо

```bash
chmod +x ./deploy.sh
./deploy.sh
```

`create_env.py` создаёт закрытый файл `secrets/default_users.json` с двумя
учётными записями и случайными паролями:

- `admin` — администратор;
- `operator` — оператор расписания.

Файл имеет права `0600`, исключён из Git и подключается к backend-контейнеру
только для чтения. При запуске создаются только отсутствующие пользователи:
существующие пароли, роли и имена никогда не перезаписываются содержимым JSON.
Посмотреть формат без реальных паролей можно в
[`secrets/default_users.example.json`](secrets/default_users.example.json).

Если `.env` уже существует, а файла пользователей ещё нет, создайте только его:

```bash
python3 create_env.py --users-only
```

После первого запуска смените сгенерированные пароли интерактивной командой.
JSON после этого не вернёт старые пароли, поскольку существующие записи не
обновляются:

```bash
docker compose exec backend python -m manage_users set-password --username admin
docker compose exec backend python -m manage_users set-password --username operator
```

Дополнительные команды управления учётными записями:

```bash
docker compose exec backend python -m manage_users create-user \
  --username editor \
  --display-name "Редактор расписания" \
  --role operator
docker compose exec backend python -m manage_users list-users
docker compose exec backend python -m manage_users disable-user --username admin
docker compose exec backend python -m manage_users enable-user --username admin
```

После запуска доступны:

- интерфейс: `http://localhost`;
- OpenAPI: `http://localhost:8000/docs`;
- liveness: `http://localhost:8000/health/live`;
- readiness с проверкой PostgreSQL: `http://localhost:8000/health/ready`.

При старте backend применяет Alembic-миграции. Перед развёртыванием в
production замените пароль PostgreSQL, задайте точные `CORS_ORIGINS` и
`ALLOWED_HOSTS`. При публикации через HTTPS установите
`AUTH_COOKIE_SECURE=true`; TLS следует завершать на reverse proxy или ingress.
Не публикуйте backend-порт `8000` во внешнюю сеть — браузер должен обращаться к
API через Nginx по тому же origin, что и к интерфейсу.

### Расчёт на рабочем компьютере

1. Настройте неделю или семестр и нажмите «Скачать задачу для ноутбука».
2. Поместите полученный файл в каталог `calculations`.
3. Выполните расчёт контейнером:

```bash
mkdir -p calculations
docker compose --profile local-solver run --rm solver-local \
  solve /data/semester.scheduler-task \
  --output /data/semester.scheduler-result \
  --workers 4
```

4. В разделе «Реестр расчётов» нажмите «Загрузить результат» и выберите
   `.scheduler-result`.

Контейнеру локального решателя не нужны PostgreSQL, Redis или доступ к серверу.
Пакет содержит неизменяемый снимок исходных данных; сервер принимает результат
только при совпадении UUID и SHA-256 снимка и повторно проверяет слоты,
конфликты ресурсов и аудитории.
Файлы могут содержать ФИО преподавателей и параметры учебной нагрузки, поэтому
их следует хранить и передавать как служебные данные.

Без Docker локальный решатель запускается из установленного backend-окружения:

```bash
cd src/app
python -m offline_solver solve ../../calculations/semester.scheduler-task \
  --output ../../calculations/semester.scheduler-result \
  --workers 4
```

Для включения прежнего серверного расчёта запустите профиль `solver` и явно
разрешите эту возможность:

```bash
SERVER_SOLVER_ENABLED=true docker compose --profile solver up --build
```

## Локальная разработка

### Backend

```bash
python3 create_env.py
pip install -r src/requirements-dev.txt
alembic -c src/alembic.ini upgrade head
uvicorn main:app --app-dir src/app --reload
```

Если локальная SQLite-база была создана старой версией приложения до
внедрения Alembic и в ней нет таблицы `alembic_version`, сначала сделайте
резервную копию. Только для исходной схемы старого приложения отметьте
начальную ревизию, затем примените остальные миграции:

```bash
alembic stamp 20260716_0001
alembic upgrade head
```

Readiness endpoint возвращает `503`, если база недоступна или её ревизия
отстаёт от текущей миграции.

При таком запуске backend прочитает `secrets/default_users.json` из корня
проекта и автоматически создаст пользователей `admin` и `operator`.

Для опциональных фоновых расчётов также запустите Redis и Celery worker:

```bash
cd src/app
celery --app=worker.celery_app worker --loglevel=INFO --concurrency=4
```

### Frontend

```bash
cd spa
npm install
npm run dev
```

Интерфейс разработки будет доступен по адресу `http://localhost:5173`.

## Проверки

```bash
python -m ruff check src/app
python -m pytest
pip-audit -r src/requirements.txt
cd spa && npm run validate && npm audit
docker compose --env-file .env.example config --quiet
```

## Документация

HTML-портал находится в [`documentation_sirius/build/html/index.html`](documentation_sirius/build/html/index.html). Его исходники и инструкция по сборке — в [`documentation_sirius`](documentation_sirius/README.md).

Дополнительные технические материалы:

- [недельное планирование](docs/STAGE_1_WEEKLY_PLANNING.md);
- [масштабируемая генерация и CP-SAT](docs/STAGE_2_SCALABLE_GENERATION.md);
- [справочники и профили правил](docs/STAGE_3_REFERENCE_DATA.md);
- [версии, публикация и диагностика](docs/STAGE_4_PRODUCTION_LIFECYCLE.md).

## Дальнейшее развитие

- личные кабинеты преподавателей и уведомления;
- экспорт календарей в iCal;
- аналитика качества расписания и загрузки ресурсов.
