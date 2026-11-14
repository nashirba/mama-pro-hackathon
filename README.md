# Особенный путь с Мама Про

Code name: kamqor.

Web platform for finding verified specialists, centres and trained nannies for children with developmental needs in Kazakhstan. Interface in Russian and Kazakh.

This is a demo MVP: it contains what the demo needs. Production hardening comes with a rewrite after the MVP is approved.

## What is in the demo

- Catalog of specialists with search and filters: city and district, specialization, developmental condition, child age, price per session or per month, format, language, experience. Only fully verified profiles reach the catalog, so every card carries one "Проверено Мама Про" mark instead of a list of verification levels.
- Results as a list or on a map (MapLibre + OpenFreeMap). On the specialist page: "Open in 2GIS" links and a WhatsApp contact button.
- Landing pages "type × city" and "condition × city", for example `/ru/almaty/logoped/`.
- Trained nannies section `/ru/nannies/` (city landing `/ru/almaty/nannies/`, nanny page `/ru/nanny/<slug>/`). A nanny is a separate profile category, not a specialist type, so nannies and specialists never mix. A nanny is shown only with a course certificate, a pediatric first aid course and a criminal record certificate date (`apps/catalog/visibility.py`). Filters: city and district, child age, condition, pay unit (hour, night, month), price per hour and per month, language, experience. No map: a nanny works at the family's home.
- Community feed: parents and specialists post questions, stories and specialist reviews, with photos, comments, replies and likes. Guests read; writing needs sign-in and a nickname. Search and filters (type, condition, city, specialist), complaints and moderation in Django admin.
- Mama Pro foundation page `/ru/mamapro/` (header link «Мама Про»): links to the upcoming course announcements and the foundation's courses on its own site, a «coming soon» stub for online courses, the five branches with their Instagram pages, and the Kaspi QR page for donations.
- Login by phone and one-time code. In the demo no SMS is sent: the code is `0000` and is shown on the page.
- Registration: after the code a new user enters last and first name and chooses who they are: mother, specialist or nanny (`/ru/register/`).
- Specialist and nanny onboarding: the questionnaire (`/ru/cabinet/application/`), document scans and a nanny's courses, "send for review", then manual review in Django admin ("Заявки специалистов и нянь"): approve (the profile, its service and search rows are created), return for changes with a comment, or reject (the phone number goes to the block list and cannot apply again). Documents are stored in the database and served only to the owner and staff.
- Parent cabinet `/ru/cabinet/`: in the cabinet the parent edits their data (last name, first name, birth date), changes the phone number with an SMS code and adds, edits and deletes child profiles (first name, last name, birth date, sex; age is computed).
- City in the header: the parent picks a city once (cookie `city`, one year), and `/ru/specialists/` and `/ru/nannies/` without query parameters open filtered by it; the home page city field is preselected. «Любой город» clears the choice.
- Mobile bottom navigation (hidden on desktop): Home, Community, Favorites, Search (catalog with the search field focused), Cabinet; the current section is highlighted.
- Favorites: a heart on catalog cards and on specialist and nanny pages adds the profile to favorites (HTMX, plain POST without JS; guests go to login). `/ru/favorites/` lists specialists, then nannies, newest first, and is linked from the cabinet. Profiles that stopped passing the visibility rules are not shown.
- Synthetic demo data: 80 specialists and 24 nannies in Almaty, Astana, Shymkent, Karaganda and Aktobe (3 nannies break the visibility rule on purpose and are not shown). Profiles, courses and certificates are fictional; every demo profile is marked as fully verified.

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

- `apps/core`: home page, language switching, city in the header, healthz
- `apps/accounts`: phone + OTP login, registration step (last and first name, role), logout from all devices
- `apps/onboarding`: specialist and nanny questionnaire, documents, review decisions, blocked phones
- `apps/favorites`: favorites (model, heart toggle, favorites page)
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
