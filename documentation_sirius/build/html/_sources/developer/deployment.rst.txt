Развёртывание и сопровождение
=============================

Контейнерная конфигурация описана в ``docker-compose.yml``. В состав входят
``postgres``, ``redis``, ``backend``, ``worker`` и ``frontend``.

Настройка
---------

Скопируйте ``.env.example`` в ``.env`` и задайте безопасные значения:

* ``POSTGRES_USER``, ``POSTGRES_PASSWORD``, ``POSTGRES_DATABASE``;
* ``CORS_ORIGINS``;
* ``CELERY_WORKER_CONCURRENCY``.

Запуск
------

.. code-block:: bash

   docker compose --env-file .env up -d --build
   docker compose ps

Backend готов, когда возвращает ``200`` на ``/health/live``. Готовность к
работе с БД проверяется через ``/health/ready``. Backend применяет миграции при
``RUN_MIGRATIONS=true``; worker миграции не запускает.

Миграции
--------

.. code-block:: bash

   cd src
   alembic upgrade head
   alembic check

Перед production-миграцией обязательно выполните и проверьте резервное
копирование PostgreSQL. Не изменяйте структуру БД вручную.

Контроль качества
-----------------

.. code-block:: bash

   ruff check src/app
   python -m pytest
   cd spa && npm run build
   docker compose --env-file .env.example config --quiet

Резервное копирование
---------------------

Регулярно сохраняйте дамп PostgreSQL, том ``uploads`` и при необходимости
``backend_logs``. После обновления проверьте параллельный запуск, отмену,
повторный расчёт, конфликтное перемещение записи, фиксацию занятия,
публикацию версии и Excel-экспорт.
