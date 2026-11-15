# Демо-деплой kamqor (Render free + Neon free)

Приложение собирается из `Dockerfile` и запускается на бесплатном web service Render. База данных - внешний PostgreSQL с PostGIS (Neon free). Деплой выполняет пользователь: репозиторий должен быть доступен Render (GitHub или GitLab).

## Условия бесплатных тарифов

Дата проверки: 2026-11-11. Условия меняются, перед деплоем сверьте их ещё раз: https://render.com/docs/free и https://neon.com/docs/introduction/plans.

Render (free web service), по документации на дату проверки:

- Сервис засыпает после 15 минут без входящих запросов. Первый запрос после простоя медленный: сервис просыпается около минуты, браузер показывает страницу загрузки. При каждом пробуждении выполняются `migrate` и `seed_demo`, это добавляет время.
- 750 бесплатных instance hours в месяц на workspace; когда они кончаются, бесплатные web service приостанавливаются до следующего месяца.
- Локальная файловая система не сохраняется между redeploy, restart и пробуждением; persistent disk недоступен; масштабирование - один instance.
- Бесплатный Render Postgres живёт 30 дней после создания (затем 14 дней grace period и удаление), поэтому для демо взят Neon.

Neon (Free plan), по документации на дату проверки:

- 1 GB хранилища на проект, 100 CU-hours в месяц на проект.
- Compute засыпает после 5 минут простоя (отключить нельзя), первый запрос после этого чуть медленнее.
- PostGIS поддерживается: `CREATE EXTENSION postgis;`.

Не удалось подтвердить по документации: доступность Docker runtime именно на free plan Render (страницы Render это не оговаривают) и версию PostGIS в Neon. Если Render не даст создать docker-сервис на free plan, переключитесь на доступный тариф или другой хостинг.

## Шаги

1. Создайте проект в Neon в регионе AWS `eu-central-1` (Frankfurt): сервис Render создаётся в `region: frankfurt`, и база должна быть в том же регионе, иначе каждый запрос получает лишнюю сетевую задержку. Скопируйте connection string: в Neon Connect выключите Connection pooling и возьмите прямую (не pooled) строку, хост без `-pooler`. Pooler работает в transaction mode, и для миграций и поиска нужно прямое подключение. Если всё же указан хост с `-pooler`, приложение само отключает server-side cursors (`DISABLE_SERVER_SIDE_CURSORS`), но для `migrate` прямая строка надёжнее. В SQL Editor выполните:

   ```sql
   CREATE EXTENSION postgis;
   ```

   Расширение `pg_trgm` создаёт миграция `apps/search`.

2. В Render выберите New - Blueprint, подключите репозиторий. Render прочитает `render.yaml` и создаст web service `kamqor-demo` (`runtime: docker`, `plan: free`, `region: frankfurt`, health check `/healthz`). Образ собирается из `Dockerfile`: `uv sync`, `tailwind build` (скачивает Tailwind CLI для архитектуры Render, linux/amd64), `collectstatic`, `compilemessages`.

3. Задайте переменные окружения (Render запросит значения с `sync: false` при создании Blueprint):

   - `DATABASE_URL` - connection string Neon. Схема любая из `postgres://`, `postgresql://`, `postgis://`: приложение принудительно использует PostGIS-бэкенд. Для Neon нужен `?sslmode=require` в конце строки (Neon обычно добавляет его сам). Используйте прямую строку без `-pooler`.
   - `ALLOWED_HOSTS` - нужен только для собственных доменов, например `demo.example.kz` (без схемы, несколько - через запятую). Хост `*.onrender.com` приложение добавляет само из переменной `RENDER_EXTERNAL_HOSTNAME`, которую Render задаёт автоматически; для первого деплоя оставьте `ALLOWED_HOSTS` пустым.
   - `DEMO_CONTACT_PHONE` - номер команды в формате `+77XXXXXXXXX`, опционально. Пока значение пустое, кнопки WhatsApp и телефона отключены. Номера других людей сюда не вписывать.
   - `DEPLOY_PROFILE=demo` и `SECRET_KEY` уже заданы в `render.yaml` (`SECRET_KEY` генерирует Render).

4. Запустите deploy. При каждом старте `dockerCommand: ./scripts/start.sh` выполняет `migrate --noinput` и `seed_demo --if-empty`, затем запускает gunicorn на `$PORT`. `--if-empty` пропускает seed, если в базе уже есть search offers: полный seed идёт десятки минут, и без этого флага каждое пробуждение сервиса стало бы таким же долгим. Чтобы пересоздать демо-данные (например, после изменения данных seed), выполните `python manage.py seed_demo` без флага в Render Shell.

5. Проверьте endpoint:

   ```
   curl -s https://<host>.onrender.com/healthz
   ```

   Ожидаемый ответ: `{"status": "ok", "db": "ok"}`. Затем откройте `/ru/specialists/` (демо-данные) и `/kk/` (казахский интерфейс).

## Локальная проверка образа

```
docker compose up --build -d web
curl -s localhost:8000/healthz
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py seed_demo
docker compose stop web
```

В compose сервис `web` обращается к БД по адресу `db:5432`. Сборка требует доступа в сеть: `tailwind build` скачивает бинарник Tailwind CLI с GitHub.
