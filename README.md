# Python Twitch History

> Python Flask app to shows the history of twitch follows and a timelapse of follow history
Production build: https://twitchhistory.herokuapp.com/
Development build: https://twitchhistorydev.herokuapp.com/

# Create a client id and client secret
Go to twitch.tv and create an account
After logging into an account enter https://dev.twitch.tv/console and click to register your application. 
Enter a name of your choice.
set the redirect url to: http://localhost:5000/login
click the analytics/tools category
click create

# Create a local database with postgresql
Create your own Master Password and login
Create a database
Get the database url for the database

# Create a Local ENV file in the directory, replace values
CLIENT_ID='cilent id code'
CILENT_SECRET='cilent secret'
POSTGRESQL_DATABASE_URI= ''
REDIRECT_URI='http://localhost:5000/login'
SECRET_KEY='secretkeycanbeanything'
ENV='dev'
REDISTOGO_URL='redis://localhost:6379'
 
# Windows Installation of redis server
install \url{https://github.com/tporadowski/redis/releases/tag/v5.0.10}. 
redis-server
redis-cli

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

# Worker Start
```bash
# setup environment
pipenv shell
pipenv install

#Setup worker
python worker.py
```