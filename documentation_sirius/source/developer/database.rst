Схема и словарь данных
=======================

Страница генерируется из ``src/app/database/all_models.py``. После изменения моделей запустите ``python tools/generate_er_diagrams.py``, затем ``python tools/generate_sphinx_database_docs.py`` и пересоберите Sphinx.

Обзорная ER-схема
-------------------

.. image:: /_static/data_model.svg
   :alt: Логическая модель данных системы расписания
   :width: 100%

На схеме показаны основные домены данных и направление логических связей. Детализация до полей приведена в модульных ER-схемах и каталоге таблиц ниже.

Модульные ER-схемы
--------------------

Карточка таблицы содержит ключевые поля: ``PK`` — первичный ключ, ``FK`` — внешний ключ. Стрелка направлена от таблицы с внешним ключом к связанной таблице.

Справочники и ресурсы
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: /_static/er/er_reference.svg
   :alt: ER-схема справочников и ресурсов
   :width: 100%

Учебные данные
~~~~~~~~~~~~~~~~

.. image:: /_static/er/er_education.svg
   :alt: ER-схема учебных данных
   :width: 100%

Планирование и доступность
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: /_static/er/er_planning.svg
   :alt: ER-схема планирования и доступности
   :width: 100%

Расчёт и диагностика
~~~~~~~~~~~~~~~~~~~~~

.. image:: /_static/er/er_generation.svg
   :alt: ER-схема расчёта и диагностики
   :width: 100%

Версия расписания
~~~~~~~~~~~~~~~~~~

.. image:: /_static/er/er_schedule.svg
   :alt: ER-схема версии расписания
   :width: 100%

Логические цепочки
--------------------

.. code-block:: text

   import_batch → stream → stream_group → student_group

   academic_period → planning_week → weekly_lesson_demand → stream

   planning_week → generation_task → generation_component / generation_issue / generation_lock

   generation_task → schedule_entry ← stream / teacher / room

   building → room → room_feature_link → room_feature

   rule_profile → rule_setting; availability_rule → teacher / student_group / room

Каталог таблиц
----------------

department
~~~~~~~~~~

Подразделения Университета «Сириус».

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``code``
     - String
     - nullable; уникальное
     - Код справочной записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —

activity_type
~~~~~~~~~~~~~

Типы учебных занятий и требования к аудитории.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``code``
     - String
     - обязательное; уникальное
     - Код справочной записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —
   * - ``room_type``
     - String
     - nullable
     - Тип аудитории.
     - —
   * - ``is_shared_for_groups``
     - Boolean
     - обязательное; default: False
     - Служебное или предметное поле «is_shared_for_groups».
     - —
   * - ``color``
     - String
     - nullable
     - Цвет отображения.
     - —
   * - ``is_active``
     - Boolean
     - обязательное; default: True
     - Признак активности записи.
     - —

discipline
~~~~~~~~~~

Справочник дисциплин.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``full_name``
     - String
     - обязательное; уникальное
     - Полное наименование.
     - —
   * - ``short_name``
     - String
     - nullable
     - Краткое наименование.
     - —
   * - ``external_id``
     - String
     - nullable; уникальное
     - Внешний идентификатор.
     - —

building
~~~~~~~~

Корпуса Университета.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``code``
     - String
     - nullable; уникальное
     - Код справочной записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —
   * - ``address``
     - String
     - nullable
     - Адрес корпуса.
     - —

room
~~~~

Аудитории и их ресурсные характеристики.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``building_id``
     - Integer
     - FK → building.id; nullable
     - Служебное или предметное поле «building_id».
     - building.id
   * - ``owner_department_id``
     - Integer
     - FK → department.id; nullable
     - Служебное или предметное поле «owner_department_id».
     - department.id
   * - ``code``
     - String
     - обязательное
     - Код справочной записи.
     - —
   * - ``name``
     - String
     - nullable
     - Наименование записи.
     - —
   * - ``floor``
     - Integer
     - nullable
     - Служебное или предметное поле «floor».
     - —
   * - ``capacity``
     - Integer
     - обязательное
     - Вместимость аудитории.
     - —
   * - ``room_type``
     - String
     - обязательное; default: 'mixed'
     - Тип аудитории.
     - —
   * - ``is_active``
     - Boolean
     - обязательное; default: True
     - Признак активности записи.
     - —

room_feature
~~~~~~~~~~~~

Справочник оснащения аудиторий.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``code``
     - String
     - обязательное; уникальное
     - Код справочной записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —

room_feature_link
~~~~~~~~~~~~~~~~~

Связь аудитории с единицей оснащения.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``room_id``
     - Integer
     - FK → room.id; обязательное
     - Строковый код аудитории.
     - room.id
   * - ``feature_id``
     - Integer
     - FK → room_feature.id; обязательное
     - Служебное или предметное поле «feature_id».
     - room_feature.id

rule_profile
~~~~~~~~~~~~

Наборы правил оптимизации.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —
   * - ``description``
     - String
     - nullable
     - Текстовое описание.
     - —
   * - ``education_level``
     - String
     - nullable
     - Служебное или предметное поле «education_level».
     - —
   * - ``is_default``
     - Boolean
     - обязательное; default: False
     - Служебное или предметное поле «is_default».
     - —
   * - ``is_active``
     - Boolean
     - обязательное; default: True
     - Признак активности записи.
     - —

rule_setting
~~~~~~~~~~~~

Настройки правил внутри профиля.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``profile_id``
     - Integer
     - FK → rule_profile.id; обязательное
     - Служебное или предметное поле «profile_id».
     - rule_profile.id
   * - ``rule_code``
     - String
     - обязательное
     - Служебное или предметное поле «rule_code».
     - —
   * - ``enabled``
     - Boolean
     - обязательное; default: True
     - Служебное или предметное поле «enabled».
     - —
   * - ``is_hard``
     - Boolean
     - обязательное; default: False
     - Жёсткость ограничения.
     - —
   * - ``weight``
     - Integer
     - обязательное; default: 5
     - Вес мягкого правила (1–10).
     - —

import_batch
~~~~~~~~~~~~

История загрузок исходных учебных данных.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``filename``
     - String
     - обязательное
     - Имя импортированного файла.
     - —
   * - ``file_path``
     - String
     - nullable
     - Путь к сохранённому файлу.
     - —
   * - ``file_type``
     - Enum(FileType)
     - обязательное
     - Тип файла или данных.
     - —
   * - ``created_date``
     - DateTime
     - nullable; default: datetime.datetime.now
     - Дата и время создания.
     - —
   * - ``status``
     - String
     - nullable; default: 'completed'
     - Текущее состояние.
     - —
   * - ``error_message``
     - String
     - nullable
     - Описание ошибки.
     - —

teacher
~~~~~~~

Преподаватели и их параметры.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``department_id``
     - Integer
     - FK → department.id; nullable
     - Служебное или предметное поле «department_id».
     - department.id
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —
   * - ``position``
     - String
     - nullable
     - Служебное или предметное поле «position».
     - —
   * - ``restrictions_json``
     - String
     - nullable
     - Служебное или предметное поле «restrictions_json».
     - —

stream
~~~~~~

Учебные потоки, из которых строится расписание.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``import_batch_id``
     - Integer
     - FK → import_batch.id; обязательное
     - Служебное или предметное поле «import_batch_id».
     - import_batch.id
   * - ``teacher_id``
     - Integer
     - FK → teacher.id; nullable
     - Служебное или предметное поле «teacher_id».
     - teacher.id
   * - ``discipline_id``
     - Integer
     - FK → discipline.id; nullable
     - Служебное или предметное поле «discipline_id».
     - discipline.id
   * - ``activity_type_id``
     - Integer
     - FK → activity_type.id; nullable
     - Служебное или предметное поле «activity_type_id».
     - activity_type.id
   * - ``required_room_id``
     - Integer
     - FK → room.id; nullable
     - Служебное или предметное поле «required_room_id».
     - room.id
   * - ``event_name``
     - String
     - обязательное
     - Наименование занятия.
     - —
   * - ``stream_type``
     - String
     - nullable
     - Тип занятия в потоке.
     - —
   * - ``lessons_count``
     - Integer
     - nullable; default: 1
     - Количество занятий.
     - —
   * - ``is_ignored``
     - Boolean
     - nullable; default: False
     - Исключить поток из расчёта.
     - —
   * - ``starts_on``
     - Date
     - nullable
     - Дата начала действия.
     - —
   * - ``ends_on``
     - Date
     - nullable
     - Дата окончания действия.
     - —

stream_feature_requirement
~~~~~~~~~~~~~~~~~~~~~~~~~~

Требования потока к оснащению аудитории.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``stream_id``
     - Integer
     - FK → stream.id; обязательное
     - Служебное или предметное поле «stream_id».
     - stream.id
   * - ``feature_id``
     - Integer
     - FK → room_feature.id; обязательное
     - Служебное или предметное поле «feature_id».
     - room_feature.id
   * - ``is_hard``
     - Boolean
     - обязательное; default: True
     - Жёсткость ограничения.
     - —

stream_group
~~~~~~~~~~~~

Связь учебного потока с группой.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``stream_id``
     - Integer
     - FK → stream.id; обязательное
     - Служебное или предметное поле «stream_id».
     - stream.id
   * - ``student_group_id``
     - Integer
     - FK → student_group.id; nullable
     - Служебное или предметное поле «student_group_id».
     - student_group.id
   * - ``group_name``
     - String
     - обязательное
     - Наименование учебной группы.
     - —
   * - ``group_size``
     - Integer
     - обязательное
     - Численность группы.
     - —

student_group
~~~~~~~~~~~~~

Учебные группы и их параметры нагрузки.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``name``
     - String
     - обязательное; уникальное
     - Наименование записи.
     - —
   * - ``specialty``
     - String
     - nullable
     - Направление подготовки.
     - —
   * - ``course``
     - Integer
     - nullable
     - Курс обучения.
     - —
   * - ``education_form``
     - String
     - nullable
     - Форма обучения.
     - —
   * - ``student_count``
     - Integer
     - обязательное; default: 0
     - Численность обучающихся.
     - —
   * - ``min_weekly_lessons``
     - Integer
     - nullable
     - Служебное или предметное поле «min_weekly_lessons».
     - —
   * - ``max_weekly_lessons``
     - Integer
     - nullable
     - Служебное или предметное поле «max_weekly_lessons».
     - —

availability_rule
~~~~~~~~~~~~~~~~~

Ограничения и предпочтения доступности.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``teacher_id``
     - Integer
     - FK → teacher.id; nullable
     - Служебное или предметное поле «teacher_id».
     - teacher.id
   * - ``student_group_id``
     - Integer
     - FK → student_group.id; nullable
     - Служебное или предметное поле «student_group_id».
     - student_group.id
   * - ``room_id``
     - Integer
     - FK → room.id; nullable
     - Строковый код аудитории.
     - room.id
   * - ``is_global``
     - Boolean
     - обязательное; default: False
     - Служебное или предметное поле «is_global».
     - —
   * - ``rule_kind``
     - String
     - обязательное
     - Служебное или предметное поле «rule_kind».
     - —
   * - ``recurrence``
     - String
     - обязательное
     - Служебное или предметное поле «recurrence».
     - —
   * - ``weekday``
     - Integer
     - nullable
     - День недели (0 — понедельник).
     - —
   * - ``specific_date``
     - Date
     - nullable
     - Конкретная дата действия правила.
     - —
   * - ``starts_on``
     - Date
     - nullable
     - Дата начала действия.
     - —
   * - ``ends_on``
     - Date
     - nullable
     - Дата окончания действия.
     - —
   * - ``lesson_start``
     - Integer
     - обязательное
     - Первый номер пары.
     - —
   * - ``lesson_end``
     - Integer
     - обязательное
     - Последний номер пары.
     - —
   * - ``is_hard``
     - Boolean
     - обязательное; default: True
     - Жёсткость ограничения.
     - —
   * - ``weight``
     - Integer
     - обязательное; default: 5
     - Вес мягкого правила (1–10).
     - —
   * - ``description``
     - String
     - nullable
     - Текстовое описание.
     - —

academic_period
~~~~~~~~~~~~~~~

Учебные периоды (например, семестры).

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``name``
     - String
     - обязательное
     - Наименование записи.
     - —
   * - ``period_type``
     - String
     - обязательное; default: 'semester'
     - Тип учебного периода.
     - —
   * - ``education_level``
     - String
     - nullable
     - Служебное или предметное поле «education_level».
     - —
   * - ``starts_on``
     - Date
     - обязательное
     - Дата начала действия.
     - —
   * - ``ends_on``
     - Date
     - обязательное
     - Дата окончания действия.
     - —
   * - ``status``
     - String
     - обязательное; default: 'draft'
     - Текущее состояние.
     - —
   * - ``created_at``
     - DateTime
     - обязательное; default: datetime.datetime.utcnow
     - Дата и время создания.
     - —

planning_week
~~~~~~~~~~~~~

Недели внутри учебного периода.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``period_id``
     - Integer
     - FK → academic_period.id; обязательное
     - Служебное или предметное поле «period_id».
     - academic_period.id
   * - ``sequence_number``
     - Integer
     - обязательное
     - Порядковый номер недели.
     - —
   * - ``starts_on``
     - Date
     - обязательное
     - Дата начала действия.
     - —
   * - ``ends_on``
     - Date
     - обязательное
     - Дата окончания действия.
     - —
   * - ``status``
     - String
     - обязательное; default: 'draft'
     - Текущее состояние.
     - —

weekly_lesson_demand
~~~~~~~~~~~~~~~~~~~~

Недельная нагрузка конкретного потока.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``week_id``
     - Integer
     - FK → planning_week.id; обязательное
     - Служебное или предметное поле «week_id».
     - planning_week.id
   * - ``stream_id``
     - Integer
     - FK → stream.id; обязательное
     - Служебное или предметное поле «stream_id».
     - stream.id
   * - ``lessons_count``
     - Integer
     - обязательное
     - Количество занятий.
     - —
   * - ``priority``
     - Integer
     - обязательное; default: 5
     - Приоритет нагрузки (1–10).
     - —

generation_task
~~~~~~~~~~~~~~~

Задание и версия расчёта расписания.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``planning_week_id``
     - Integer
     - FK → planning_week.id; nullable
     - Служебное или предметное поле «planning_week_id».
     - planning_week.id
   * - ``parent_task_id``
     - Integer
     - FK → generation_task.id; nullable
     - Служебное или предметное поле «parent_task_id».
     - generation_task.id
   * - ``semester_batch_id``
     - String
     - nullable
     - Служебное или предметное поле «semester_batch_id».
     - —
   * - ``version_number``
     - Integer
     - обязательное; default: 1
     - Номер версии расчёта.
     - —
   * - ``publication_status``
     - String
     - обязательное; default: 'draft'
     - Статус публикации версии.
     - —
   * - ``published_at``
     - DateTime
     - nullable
     - Дата и время публикации.
     - —
   * - ``canceled_at``
     - DateTime
     - nullable
     - Дата и время отмены.
     - —
   * - ``edit_revision``
     - Integer
     - обязательное; default: 0
     - Номер редакции ручных правок.
     - —
   * - ``created_at``
     - DateTime
     - nullable; default: datetime.datetime.utcnow
     - Дата и время создания.
     - —
   * - ``status``
     - String
     - nullable; default: 'pending'
     - Текущее состояние.
     - —
   * - ``start_date``
     - DateTime
     - nullable
     - Начало диапазона расчёта.
     - —
   * - ``end_date``
     - DateTime
     - nullable
     - Конец диапазона расчёта.
     - —
   * - ``groups_json``
     - String
     - nullable
     - Служебное или предметное поле «groups_json».
     - —
   * - ``holidays_json``
     - String
     - nullable
     - Служебное или предметное поле «holidays_json».
     - —
   * - ``settings_json``
     - String
     - nullable
     - Служебное или предметное поле «settings_json».
     - —
   * - ``result_count``
     - Integer
     - nullable; default: 0
     - Количество записей результата.
     - —
   * - ``error_message``
     - String
     - nullable
     - Описание ошибки.
     - —
   * - ``total_components``
     - Integer
     - обязательное; default: 0
     - Служебное или предметное поле «total_components».
     - —
   * - ``completed_components``
     - Integer
     - обязательное; default: 0
     - Служебное или предметное поле «completed_components».
     - —
   * - ``progress_percent``
     - Integer
     - обязательное; default: 0
     - Прогресс выполнения в процентах.
     - —
   * - ``metrics_json``
     - String
     - nullable
     - Служебное или предметное поле «metrics_json».
     - —
   * - ``celery_workflow_id``
     - String
     - nullable
     - Служебное или предметное поле «celery_workflow_id».
     - —
   * - ``celery_root_task_id``
     - String
     - nullable
     - Служебное или предметное поле «celery_root_task_id».
     - —
   * - ``celery_component_ids_json``
     - String
     - nullable
     - Служебное или предметное поле «celery_component_ids_json».
     - —

generation_lock
~~~~~~~~~~~~~~~

Блокировка области параллельного расчёта.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``scope_key``
     - String
     - PK; nullable
     - Ключ заблокированной области.
     - —
   * - ``task_id``
     - Integer
     - FK → generation_task.id; обязательное
     - Служебное или предметное поле «task_id».
     - generation_task.id
   * - ``created_at``
     - DateTime
     - обязательное; default: datetime.datetime.utcnow
     - Дата и время создания.
     - —

generation_issue
~~~~~~~~~~~~~~~~

Диагностика расчёта и неразмещённой нагрузки.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``task_id``
     - Integer
     - FK → generation_task.id; обязательное
     - Служебное или предметное поле «task_id».
     - generation_task.id
   * - ``kind``
     - String
     - обязательное
     - Тип диагностической проблемы.
     - —
   * - ``severity``
     - String
     - обязательное; default: 'warning'
     - Критичность проблемы.
     - —
   * - ``message``
     - String
     - обязательное
     - Текст диагностического сообщения.
     - —
   * - ``stream_id``
     - Integer
     - FK → stream.id; nullable
     - Служебное или предметное поле «stream_id».
     - stream.id
   * - ``group_name``
     - String
     - nullable
     - Наименование учебной группы.
     - —
   * - ``date``
     - Date
     - nullable
     - Дата занятия.
     - —
   * - ``lesson_number``
     - Integer
     - nullable
     - Номер пары.
     - —
   * - ``details_json``
     - String
     - nullable
     - Служебное или предметное поле «details_json».
     - —
   * - ``created_at``
     - DateTime
     - обязательное; default: datetime.datetime.utcnow
     - Дата и время создания.
     - —

generation_component
~~~~~~~~~~~~~~~~~~~~

Компонент декомпозированного расчёта.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``task_id``
     - Integer
     - FK → generation_task.id; обязательное
     - Служебное или предметное поле «task_id».
     - generation_task.id
   * - ``component_key``
     - String
     - обязательное
     - Ключ компонента расчёта.
     - —
   * - ``status``
     - String
     - обязательное; default: 'queued'
     - Текущее состояние.
     - —
   * - ``event_count``
     - Integer
     - обязательное; default: 0
     - Количество занятий в компоненте.
     - —
   * - ``variable_count``
     - Integer
     - обязательное; default: 0
     - Число переменных solver.
     - —
   * - ``constraint_count``
     - Integer
     - обязательное; default: 0
     - Число ограничений solver.
     - —
   * - ``solve_seconds``
     - Float
     - nullable
     - Время решения компонента.
     - —
   * - ``objective``
     - Float
     - nullable
     - Значение целевой функции.
     - —
   * - ``error_message``
     - String
     - nullable
     - Описание ошибки.
     - —

schedule_entry
~~~~~~~~~~~~~~

Отдельное занятие в версии расписания.

.. list-table::
   :header-rows: 1
   :widths: 16 18 24 30 20

   * - Поле
     - Тип
     - Свойства
     - Назначение
     - Связь
   * - ``id``
     - Integer
     - PK; nullable
     - Технический идентификатор записи.
     - —
   * - ``task_id``
     - Integer
     - FK → generation_task.id; nullable
     - Служебное или предметное поле «task_id».
     - generation_task.id
   * - ``planning_week_id``
     - Integer
     - FK → planning_week.id; nullable
     - Служебное или предметное поле «planning_week_id».
     - planning_week.id
   * - ``source_stream_id``
     - Integer
     - FK → stream.id; nullable
     - Служебное или предметное поле «source_stream_id».
     - stream.id
   * - ``group_name``
     - String
     - обязательное
     - Наименование учебной группы.
     - —
   * - ``event_name``
     - String
     - обязательное
     - Наименование занятия.
     - —
   * - ``stream_type``
     - String
     - обязательное
     - Тип занятия в потоке.
     - —
   * - ``teacher_id``
     - Integer
     - FK → teacher.id; nullable
     - Служебное или предметное поле «teacher_id».
     - teacher.id
   * - ``room_id``
     - String
     - nullable
     - Строковый код аудитории.
     - —
   * - ``room_ref_id``
     - Integer
     - FK → room.id; nullable
     - Служебное или предметное поле «room_ref_id».
     - room.id
   * - ``date``
     - DateTime
     - nullable
     - Дата занятия.
     - —
   * - ``lesson_number``
     - Integer
     - nullable
     - Номер пары.
     - —
   * - ``warning``
     - String
     - nullable
     - Предупреждение для занятия.
     - —
   * - ``is_locked``
     - Boolean
     - обязательное; default: False
     - Фиксация занятия от пересчёта.
     - —
   * - ``created_at``
     - DateTime
     - nullable; default: datetime.datetime.now
     - Дата и время создания.
     - —
