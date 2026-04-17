# FitTogether 

## Student Information
- **Full Name:** Juan José Álvarez Ocampo, Viviana Arango Tabares and Helen Sanabria
- **Class:** ST0251
- **Course:** Project 1
- **Professor:** Paola Andrea Vallejo Correa

---


## Environment
- **Operating System:** Windows 11 Pro, Version 10.0.22621, x64-based PC. And macOS Tahoe 26.0.1
- **Processor:** Intel64 Family 6 Model 142 Stepping 10, ~2001 MHz, and Apple Silicon M4
- **Memory:** 16 GB RAM, 512 GB 
- **Terminal:** PowerShell 5.1 and zsh 5.9 (arm64-apple-darwin25.0)

---


## Prerequisites
Before starting, make sure you have the following installed on your computer:

1. **Python 3.8 or higher**
   - Check installation: `python --version` or `python3 --version`
   - Download from: https://www.python.org/downloads/

2. **pip** (usually comes with Python)
   - Check installation: `pip --version` or `pip3 --version`

3. **Git** (optional, if you're going to clone the repository)
   - Check installation: `git --version`
   - Download from: https://git-scm.com/downloads

---

## Project Structure 

```
FitTogether
├─ README.md
├─ fittogether
│  ├─ __init__.py
│  ├─ asgi.py
│  ├─ settings.py
│  ├─ urls.py
│  ├─ utils.py
│  └─ wsgi.py
├─ manage.py
├─ posts
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ migrations
│  │  ├─ 0001_initial.py
│  │  ├─ 0002_alter_post_unique_together_alter_post_author_and_more.py
│  │  ├─ 0003_post_moderation_status.py
│  │  └─ __init__.py
│  ├─ models.py
│  ├─ services
│  │  ├─ __init__.py
│  │  └─ openai_moderation.py
│  ├─ signals.py
│  ├─ templates
│  │  └─ posts
│  │     ├─ edit_post.html
│  │     └─ not_allowed.html
│  ├─ tests.py
│  ├─ urls.py
│  └─ views.py
├─ requirements.txt
├─ social
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ context_processors.py
│  ├─ migrations
│  │  ├─ 0001_initial.py
│  │  ├─ 0002_follow_status_follow_updated_at.py
│  │  └─ __init__.py
│  ├─ models.py
│  ├─ templates
│  │  └─ social
│  │     ├─ feed.html
│  │     ├─ friend_requests.html
│  │     ├─ profile.html
│  │     └─ search.html
│  ├─ tests.py
│  ├─ urls.py
│  └─ views.py
├─ static
│  ├─ icons
│  │  ├─ comment.png
│  │  ├─ edit.png
│  │  ├─ feed.png
│  │  ├─ filter.png
│  │  ├─ friends.png
│  │  ├─ heart.png
│  │  ├─ image.png
│  │  ├─ messages.png
│  │  └─ settings.png
│  └─ images
│     └─ profile_default.jpg
├─ templates
│  ├─ base.html
│  ├─ includes
│  │  └─ streak_panel.html
│  └─ registration
│     └─ login.html
└─ users
   ├─ __init__.py
   ├─ admin.py
   ├─ apps.py
   ├─ forms.py
   ├─ migrations
   │  ├─ 0001_initial.py
   │  ├─ 0002_remove_profile_birth_date_and_more.py
   │  ├─ 0003_profile_current_weekly_streak_and_more.py
   │  ├─ 0004_profile_banner_color.py
   │  └─ __init__.py
   ├─ models.py
   ├─ signals.py
   ├─ templates
   │  └─ users
   │     ├─ profile.html
   │     └─ register.html
   ├─ tests.py
   ├─ urls.py
   └─ views.py

```

## Installation and Setup

### Step 1: Get the Code

```bash
git clone https://github.com/jalvarez01/FitTogether.git
cd fittogether
```

### Step 2: Create a Virtual Environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

When the virtual environment is activated, you'll see `(venv)` at the beginning of your command line.

### Step 3: Install Dependencies

With the virtual environment activated, install all project dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file at the project root (or update your existing one) with:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL_TEXT=gpt-4o-mini
```

This will install:

- asgiref
- certifi
- charset-normalizer
- Django
- gunicorn
- idna
- packaging
- pillow
- python-dotenv
- requests
- sqlparse
- typing_extensions
- urllib3

### Step 4: Create a Superuser (Optional)

To access Django's admin panel, create a superuser:

```bash
python manage.py createsuperuser
```

You'll be asked for:
- Username
- Email address
- Password (you type it but it won't show on screen)


### Step 5: Make Migrations 

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Run the Development Server

Start Django's local server:

```bash
python manage.py runserver
```

You'll see a message similar to:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Step 7: Open the Application

Open your web browser and visit:
- **Main application:** http://127.0.0.1:8000/ or http://localhost:8000/
- **Admin panel:** http://127.0.0.1:8000/admin/ (use superuser credentials)


---


## Useful Commands

### Stop the Server
Press `Ctrl + C` in the terminal where the server is running.

### Deactivate the Virtual Environment
```bash
deactivate
```

### Create New Migrations (after modifying models)
```bash
python manage.py makemigrations
python manage.py migrate
```

### Collect Static Files (for production)
```bash
python manage.py collectstatic
```

### Run Django Shell (for testing)
```bash
python manage.py shell
```

---


## Common Troubleshooting

### Error: "python is not recognized as a command"
- **Solution:** Make sure Python is installed and added to your system's PATH.
- Try using `python3` instead of `python`.

### Error: "No module named 'django'"
- **Solution:** Make sure you have the virtual environment activated and have run `pip install -r requirements.txt`.

### Error: "Port is already in use"
- **Solution:** Port 8000 is already being used. You can:
  - Close the other process using the port
  - Use another port: `python manage.py runserver 8001`

### Error loading images
- **Solution:** Make sure Pillow is installed correctly: `pip install Pillow`

### Migration issues
- **Solution:** Try resetting migrations:
```bash
python manage.py migrate --run-syncdb
```

---

**Last updated:** April 2026
