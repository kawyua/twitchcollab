# Python Twitch Collab

> Python Flask app to show twitch follows and display the web of followers
Production build: https://twitchcollab.herokuapp.com/
Development build: https://twitchcollabdevelopment.herokuapp.com/

## Quick Start

```bash

# Install dependencies
pipenv shell
pipenv install

# Serve on localhost:5000
python app.py

# Setting up Postgres database
python
from app import db
db.create_all()
exit()
```
