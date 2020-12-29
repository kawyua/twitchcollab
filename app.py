from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import datetime
from datetime import timedelta 
from secrets import CLIENT_ID, CILENT_SECRET, SQLALCHEMY_DATABASE_URI, POSTGRESQL_DATABASE_URI
from requests.exceptions import HTTPError

BASE_URL = 'https://api.twitch.tv/helix/'
url ='https://id.twitch.tv/oauth2/token'
access_token = ''
userdata = ''

app = Flask(__name__)

ENV = 'dev'
if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRESQL_DATABASE_URI
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI


#getting app access token
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
    #print('response?{0}'.format(response.text))
    access_token = response.json()[u'access_token']
    #print(access_token)



app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


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
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        twitchuser = request.form['twitchuser']
        if twitchuser == '':
            return render_template('index.html', message='Please enter required fields')
        headers2 = {
            'client-id': CLIENT_ID,
            'Authorization': 'Bearer {0}'.format(access_token),
        }
        params2 = (
            ('login',twitchuser),
        )
        try:
            response2 = requests.get('https://api.twitch.tv/helix/users?', headers=headers2, params=params2)

            # If the response was successful, no Exception will be raised
            response2.raise_for_status()
        except HTTPError as http_err:
            #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(http_err))

        except Exception as err:
            #print('Other error occurred: {0}'.format(err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(err))
        else:
            #print('Success!')
            #print(response2.text.encode("utf-8"))
            #print(response2.json()["data"][0]["login"])
            userdata = response2.json()
            date_time_obj = datetime.datetime.strptime((userdata["data"][0]["created_at"]), '%Y-%m-%dT%H:%M:%S.%fZ')
            context = followdeep2(userdata["data"][0]["id"])
            print(context)
            context = sorted(context.items(), key=lambda x: x[1], reverse=True)
            print("test")
            print(context)
            for i in context:
    	        print(i[0], i[1])
            return render_template('recommendations.html', 
                context = context,
                login=userdata["data"][0]["login"],
                profile_image_url=userdata["data"][0]["profile_image_url"],
                view_count=userdata["data"][0]["view_count"],
                created_at=date_time_obj.strftime("%d-%b-%Y"),
                description=userdata["data"][0]["description"],
                id=userdata["data"][0]["id"]
            )
            

@app.route('/follow', methods=['POST'], )
def follows():
    if request.method == 'POST':
        login = request.form['login']
        profile_image_url = request.form['profile_image_url']
        view_count = request.form['view_count']
        created_at = request.form['created_at']
        description = request.form['description']
        id = request.form['id']
        headers1 = {
            'client-id': CLIENT_ID,
            'Authorization': 'Bearer {0}'.format(access_token),
        }

        params1 = (
            ('from_id',id),
            ('first', 50),
        )
        try:
            response1 = requests.get('https://api.twitch.tv/helix/users/follows?', headers=headers1, params=params1)

            # If the response was successful, no Exception will be raised
            response1.raise_for_status()
        except HTTPError as http_err:
            #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
        except Exception as err:
           # print('Other error occurred: {0}'.format(err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(err))
        else:
            #print('Success!')
            #print(response1.text.encode("utf-8"))
            followdata = response1.json()
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

def followdeep2(id):
    analysis = {}
    currDate = datetime.datetime.now()
    headers1 = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }

    params1 = (
        ('from_id',id),
        ('first', 50),
    )
    
    try:
        response1 = requests.get('https://api.twitch.tv/helix/users/follows?', headers=headers1, params=params1)

        # If the response was successful, no Exception will be raised
        response1.raise_for_status()
    except HTTPError as http_err:
        #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
    except Exception as err:
        #print('Other error occurred: {0}'.format(err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(err))
    else:
        #print('Success!')
        print(response1.text.encode("utf-8"))
        followdata = response1.json()
        for twitchuser in followdata["data"]:
            params1 = (
                ('from_id',twitchuser["to_id"]),
                ('first', 50),
            )
            
            try:
                response1 = requests.get('https://api.twitch.tv/helix/users/follows?', headers=headers1, params=params1)
                # If the response was successful, no Exception will be raised
                response1.raise_for_status()
            except HTTPError as http_err:
                #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
                return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
            except Exception as err:
                #print('Other error occurred: {0}'.format(err))  # Python 3.6
                return render_template('index.html', message='Other error occurred: {0}'.format(err))
            else:
                streamerfollows = response1.json()
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

if __name__ == '__main__':
    app.run()
