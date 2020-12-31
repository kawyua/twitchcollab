from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import datetime
from datetime import timedelta 
from requests.exceptions import HTTPError
from dotenv import load_dotenv
import os
import requests


# load dotenv in the base root
#APP_ROOT = os.path.join(os.path.dirname(__file__), '..')   # refers to application_top
#dotenv_path = os.path.join(APP_ROOT, '.env')
#load_dotenv(dotenv_path)
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CILENT_SECRET = os.getenv("CILENT_SECRET")
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
POSTGRESQL_DATABASE_URI = os.getenv("POSTGRESQL_DATABASE_URI")
ENV = os.getenv("ENV")
BASE_URL = 'https://api.twitch.tv/helix/'
url ='https://id.twitch.tv/oauth2/token' 
access_token = ''
userdata = ''

app = Flask(__name__)
#def testmode(ENV):
if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRESQL_DATABASE_URI
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

'''sets access token up given a cilent id and secret
returns {"access_token":"string","expires_in":5290773,"token_type":"bearer"}
'''
try:
    response = requests.post(url, 
    data={'client_id':CLIENT_ID,
    'client_secret':CILENT_SECRET,
    'grant_type':'client_credentials'
    })

    # If the response was successful, no Exception will be raised
    response.raise_for_status()
except HTTPError as http_err:
    print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
except Exception as err:
    print('Other error occurred: {0}'.format(err))  # Python 3.6
else:
    #print('Success!')
    #Sprint('response?{0}'.format(response.text))
    access_token =  response.json()[u'access_token']
    #print(access_token)



#class Feedback(db.Model):
#    __tablename__ = 'feedback'
#    id = db.Column(db.Integer, primary_key=True)
#    customer = db.Column(db.String(200), unique=True)
#    dealer = db.Column(db.String(200))
#    rating = db.Column(db.Integer)
#    comments = db.Column(db.Text())
#
#    def __init__(self, customer, dealer, rating, comments):
#        self.customer = customer
#        self.dealer = dealer
#        self.rating = rating
#        self.comments = comments

@app.route('/')
def index():
    '''
    / is the default page, returns template index.html
    '''
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    '''
    from submission, sets the page for /submit and calls to make recommendations
    Parameters in post: twitchuser
    Returns: /submit template page
    '''
    if request.method == 'POST':
        if 'twitchuser' not in request.form:
            return 'Bad Submission', 400
        twitchuser = request.form['twitchuser']
        if twitchuser == '':
            return render_template('index.html', message='Please enter required fields')
    
        userdata = getuser(twitchuser)
        date_time_obj = datetime.datetime.strptime((userdata["data"][0]["created_at"]), '%Y-%m-%dT%H:%M:%S.%fZ')
        context = followdeep2(userdata["data"][0]["id"])
        context = sorted(context.items(), key=lambda x: x[1], reverse=True)
        return render_template('recommendations.html', 
            context = context,
            login=userdata["data"][0]["login"],
            profile_image_url=userdata["data"][0]["profile_image_url"],
            view_count=userdata["data"][0]["view_count"],
            created_at=date_time_obj.strftime("%d-%b-%Y"),
            description=userdata["data"][0]["description"],
            id=userdata["data"][0]["id"]
        )
    else:
        return'Bad Request', 400 

@app.route('/follow', methods=['POST'], )
def follows():
    '''
    sets the page for follow
    Parameters in post: login, profile_image_url, view_count
    Returns: A dictionary [username:summation value]
    '''
    if request.method == 'POST':
        login = request.form['login']
        profile_image_url = request.form['profile_image_url']
        view_count = request.form['view_count']
        created_at = request.form['created_at']
        description = request.form['description']
        id = request.form['id']
        followdata = getfollowers(id)
        #print(followdata["total"])
        return render_template('follow.html', 
            **followdata,
            login=login,
            profile_image_url=profile_image_url,
            view_count=view_count,
            created_at=created_at,
            description=description,
            id=id
        )
    else:
        return 'Bad Request', 400

def followdeep2(id):
    '''
    Makes a recommendation from tree deepness 2. followed at and follow recency to modify search values.
    Parameters: a user id
    Returns: A dictionary [username:summation value]
    '''
    analysis = {}
    currDate = datetime.datetime.now()

    followdata = getfollowers(id)

    for twitchuser in followdata["data"]:
        streamerfollows = getfollowers(twitchuser["to_id"])
        for streameruser in streamerfollows["data"]:
            date_time_obj = datetime.datetime.strptime(streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            followrecency = (currDate - date_time_obj)
            #These are test recommendations
            reliability = max(100-followrecency.days,30)/(streamerfollows["total"]*5)
            if analysis.get(streameruser["to_name"]) is None:
                analysis.update({streameruser["to_name"]:reliability})
            else:
                analysis[streameruser["to_name"]] += reliability
    return analysis

def getuser(username):
    '''
    Calls twitch api to get information of a specific userid:
    Parameters: a user name
    Returns: A json list of structure 
    {
        "data":[{
            "id":"int",
            "login":"string",
            "display_name":"string",
            "type":"",
            "broadcaster_type": null or "partner",
            "description":"string","profile_image_url":"url",
            "offline_image_url":"url",
            "view_count":int,
            "created_at":"datetime of '%Y-%m-%dT%H:%M:%SZ"}
        ]
    }
    '''
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    params = (
        ('login',username),
    )
    try:
        response = requests.get('https://api.twitch.tv/helix/users?', headers=headers, params=params)

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(http_err))

    except Exception as err:
        #print('Other error occurred: {0}'.format(err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(err))
    else:
        print(response.text.encode("utf-8"))
        return response.json()
        #print(response2.json()["data"][0]["login"])

#
def getfollowers(userID):
    '''
    Calls twitch api to get followers of a specific userid:
    Parameters: a user id
    Returns: A json list of structure 
    {
        "total":int, 
        "data":[{
            "from_id":"int",
            "from_name":"string",
            "to_id":"int",
            "to_name":"string",
            "followed_at":"datetime of '%Y-%m-%dT%H:%M:%SZ'"}
            , ...
        ],
        "pagination":{empty or int}
    }
    '''
    params = (
        ('from_id',userID),
        ('first', 50),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    
    try:
        response = requests.get('https://api.twitch.tv/helix/users/follows?', headers=headers, params=params)
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
    except Exception as err:
        #print('Other error occurred: {0}'.format(err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(err))
    else:
        #print(response.text)
        return response.json()


if __name__ == '__main__':
    app.run()
   # testmode(ENVIRONMENT)
