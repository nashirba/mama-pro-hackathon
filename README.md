# Особенный путь с Мама Про

Code name: kamqor.

Web platform for finding verified specialists, centres and trained nannies for children with developmental needs in Kazakhstan. Interface in Russian and Kazakh.

This is a demo MVP: it contains what the demo needs. Production hardening comes with a rewrite after the MVP is approved.

## What is in the demo

- Catalog of specialists with search and filters: city and district, specialization, developmental condition, child age, price per session or per month, format, language, experience, and verified documents.
- Results as a list or on a map (MapLibre + OpenFreeMap). On the specialist page: "Open in 2GIS" links and a WhatsApp contact button.
- Landing pages "type × city" and "condition × city", for example `/ru/almaty/logoped/`.
- Trained nannies section `/ru/nannies/` (city landing `/ru/almaty/nannies/`, nanny page `/ru/nanny/<slug>/`). A nanny is a separate profile category, not a specialist type, so nannies and specialists never mix. A nanny is shown only with a course certificate, a pediatric first aid course and a criminal record certificate date (`apps/catalog/visibility.py`). Filters: city and district, child age, condition, pay unit (hour, night, month), price per hour and per month, language, experience. No map: a nanny works at the family's home.
- Community feed: parents and specialists post questions, stories and specialist reviews, with photos, comments, replies and likes. Guests read; writing needs sign-in and a nickname. Search and filters (type, condition, city, specialist), complaints and moderation in Django admin.
- Mama Pro foundation page `/ru/mamapro/` (header link «Мама Про»): links to the upcoming course announcements and the foundation's courses on its own site, a «coming soon» stub for online courses, the five branches with their Instagram pages, and the Kaspi QR page for donations.
- Login by phone and one-time code. In the demo no SMS is sent: the code is `0000` and is shown on the page.
- Parent cabinet `/ru/cabinet/`: after the code a new user enters last and first name (`/ru/register/`). In the cabinet the parent edits their data (last name, first name, birth date), changes the phone number with an SMS code and adds, edits and deletes child profiles (first name, last name, birth date, sex; age is computed).
- Synthetic demo data: 80 specialists and 24 nannies in Almaty, Astana, Shymkent, Karaganda and Aktobe (3 nannies break the visibility rule on purpose and are not shown). Profiles, courses, certificates and verification badges are fictional.

## Stack

Python 3.13, Django 5.2, PostgreSQL 17 + PostGIS, django-parler for RU/KZ content, Django templates + HTMX + Alpine.js + Tailwind CSS, MapLibre GL JS, pytest, uv, Docker.

## Run locally

Requirements: [uv](https://docs.astral.sh/uv/), Docker, GDAL (`brew install gdal`), gettext (`brew install gettext`).

```bash
make install   # dependencies + .env from .env.example
make db        # PostGIS on localhost:5433
make migrate
make seed      # demo data
make messages  # compile translations (Russian needs them too: age plurals)
make run       # http://localhost:8000/ru/
```

On macOS with Apple Silicon, `.env` must point to the Homebrew GDAL/GEOS libraries. `.env.example` already does.

Or run the whole app in Docker: `make docker-up`, then open http://localhost:8000/ru/.

`make help` lists all commands.

## Tests

```bash
make test-file F=tests/search/test_query.py   # one file
make test                                      # full suite, heavy
```

Tests use `config/settings_test.py` and the PostGIS container. `compilemessages` must have run (`make messages`), otherwise age plurals fail.

## Structure

- `apps/core`: home page, language switching, healthz
- `apps/accounts`: phone + OTP login, registration step (last and first name), logout from all devices
- `apps/cabinet`: parent cabinet, child profiles, phone change
- `apps/consents`: consents at registration
- `apps/geo`: KATO (administrative units), addresses, 2GIS links
- `apps/catalog`: reference data, specialist and nanny profiles, nanny courses, services, specialist and nanny pages
- `apps/search`: search index (`SearchOffer`), filters, results and the nanny section, landings, map GeoJSON, suggestions
- `apps/community`: community feed (posts, reviews, comments, likes, complaints), visibility rules, admin moderation
- `apps/demo`: `seed_demo` command
- `config/`: settings (env-driven), URLs
- `locale/`: RU/KZ translations; `.mo` files are compiled at build time and not committed

## Deploy

The demo is deployed to Render (free plan, Docker) with a Neon PostgreSQL + PostGIS database. See `docs/deploy-demo.md`.
