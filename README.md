# Python Twitch History

> Python Flask app to shows the history of twitch follows and display the web of followers
Production build: https://twitchhistory.herokuapp.com/
Development build: https://twitchhistorydev.herokuapp.com/

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
