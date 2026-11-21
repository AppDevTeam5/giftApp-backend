# Gift App Backend

Backend for a social platform for gift giving and celebrations. Users fill in a
questionnaire to create their own profile (a "friend card"), connect with friends,
keep wishlists, save profiles for friends who are not on the app, get birthday and
festival reminders, stay within a yearly gift budget, organize group celebrations,
and get personalized gift and event ideas from an LLM.

Built with Flask, SQLAlchemy (SQLite), Gunicorn and Docker.

## Project structure

```
src/
  app.py            creates the app and registers the route files
  db.py             database models (User is written as the template; the rest are TODO)
  utils.py          shared helpers: responses, request body, get_current_user()
  routes/
    auth.py         register, login, session refresh, logout
    profile.py      my friend card (questionnaire), other users' cards
    friends.py      friend requests and friend list
    wishlist.py     my wishlist, friends' wishlists
    people.py       friends saved manually (not on the app)
    dates.py        upcoming birthdays, festivals, special days
    budget.py       gifts and yearly budget
    events.py       group celebrations and guests
    suggestions.py  LLM gift and event ideas
scripts/
  seed_festivals.py adds the shared festival dates
```

Each file in `routes/` lists its planned routes at the top. Decide together who
owns each file and write your name next to "Owner"; working in separate files
avoids merge conflicts.

## Run it locally (Windows)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
cd src
python app.py
```

Open http://localhost:8000/ and you should see `{"status": "ok"}`.

## Logging in from Postman (once auth.py is written)

1. `POST /api/register/` with `{"email": "...", "password": "...", "name": "..."}`
2. Copy `session_token` from the response.
3. On other requests: Authorization tab -> Bearer Token -> paste it.

## Conventions

- Dates are sent and returned as `"YYYY-MM-DD"` text; date-times as `"YYYY-MM-DDTHH:MM:SS"`.
- Errors look like `{"error": "message"}` with status 400, 401, 403, 404 or 409.
- Every protected route starts with `user = get_current_user()` and returns 401 if it is `None`.
- Changed a model? Delete `src/instance/giftapp.db` and restart (this deletes local test data).

## Team Git workflow

1. Before starting: switch to `main` and pull.
2. Create a branch for your feature, e.g. `liz/people-routes`.
3. Commit small steps with clear messages.
4. Push the branch and open a pull request into `main`.
5. Your partner reviews and merges it.

Never commit `.env`, `venv/` or `.db` files (they are in `.gitignore`).
