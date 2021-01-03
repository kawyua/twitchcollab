from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import datetime
from datetime import timedelta 
from dotenv import load_dotenv
import os
from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests_toolbelt import sessions


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
http = sessions.BaseUrlSession(base_url="https://api.twitch.tv/helix")
http = requests.Session()

DEFAULT_TIMEOUT = 5 # seconds

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)

# Mount it for both http and https usage
adapter = TimeoutHTTPAdapter(timeout=2.5)
http.mount("https://", adapter)
http.mount("http://", adapter)
total = 10
status_forcelist=[413, 429, 503]
method_whitelist=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
backoff_factor=0

retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
http.mount("https://", TimeoutHTTPAdapter(max_retries=retries))

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
        if 'login' not in request.form:
            return 'Bad Submission', 400
        login = request.form['login']
        if login == '':
            return render_template('index.html', message='Please enter required fields')
        print("testing submit")
        userdata = getuser(login)
        if not bool(userdata):
            return render_template('index.html', message='User doesnt exist.')
        graphdata = datatograph(userdata["data"][0]["id"])
        print(str(graphdata))
        graphdata["users"].append(userdata["data"][0])
        userdata = graphdata["users"]
        followdata = graphdata["follows"]

        return render_template('graph.html', 
            userdata = userdata,
            followdata = followdata
        )
    else:
        return'Bad Request', 400 

@app.route('/follow', methods=['POST'], )
def follow():
    '''
    sets the page for follow
    Parameters in post: login, profile_image_url, view_count
    Returns: A dictionary [username:summation value]
    '''
    if request.method == 'POST':
        if 'login' not in request.form:
            return render_template('index.html', message='Input is wrong')
        #print(request.form['login'])
        login = request.form['login']
        if login == '':
            #print("empty user")
            return render_template('index.html', message='Please enter required fields')
        userdata = getuser(login)
        if len(userdata["data"]) == 0:
            return render_template('index.html', message='User doesnt exist.')
        date_time_obj = datetime.datetime.strptime((userdata["data"][0]["created_at"]), '%Y-%m-%dT%H:%M:%S.%fZ')
        #print((userdata["data"][0]["created_at"]))
        followdata = getfollowers(userdata["data"][0]["id"])
        userIDlist = []
        for follow in followdata:
            userIDlist.append(('id',follow["to_id"]))
        #print("entering getmultiuserinfo function")
        multiuserinfo = getMultiUserInfo(userIDlist)
        totalfollows = len(followdata)

        return render_template('follow.html',
            data = multiuserinfo, 
            followdata = followdata,
            followlen = totalfollows,
            login=userdata["data"][0]["login"],
            broadcaster_type=userdata["data"][0]["broadcaster_type"],
            offlineimg=userdata["data"][0]["offline_image_url"],
            type=userdata["data"][0]["type"],
            profile_image_url=userdata["data"][0]["profile_image_url"],
            view_count=userdata["data"][0]["view_count"],
            created_at=date_time_obj.strftime("%d-%b-%Y"),
            description=userdata["data"][0]["description"],

            id=userdata["data"][0]["id"],
        )
    else:
        return 'Bad Request', 400\

def datatograph(id):
    print("entering data")
    graphoutput = {}
    followerslist = getfollowers(id)
    
    userIDlist = []
    for follow in followerslist:
        userIDlist.append(('id',follow["to_id"]))
    print("entering getmultiuserinfo function")
    multiuserinfo = getMultiUserInfo(userIDlist)
    graphoutput["users"] = multiuserinfo
    graphoutput["follows"] = followerslist
    print(str(graphoutput))
    return graphoutput

def followdeep2(id):
    '''
    Makes a recommendation from tree deepness 2. followed at and follow recency to modify search values.
    Parameters: a user id
    Returns: A dictionary [username:summation value]
    '''
    analysis = {}
    currDate = datetime.datetime.now()

    followdata = getfollowers(id)

    for twitchuser in followdata:
        streamerfollows = getfollowers(twitchuser["to_id"])
        for streameruser in streamerfollows:
            date_time_obj = datetime.datetime.strptime(streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            followrecency = (currDate - date_time_obj)
            #These are test recommendations
            reliability = max(100-followrecency.days,30)/(len(streamerfollows)*5)
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
    #print("checking user")
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
        #print(response.text.encode("utf-8"))
        return response.json()

def getMultiUserInfo(userIDlist):
    '''
    Calls twitch api to get information of multiple userid:
    Parameters:  list of user id
    Returns: a list of user data 
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
            "created_at":"datetime of '%Y-%m-%dT%H:%M:%SZ"},
            ...
        ]
    }
    '''
    #print(str(userIDlist))
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    count = 0
    userinfolist = []
    #print("entering getmultiuserinfo while loop")
    while(len(userIDlist) > count):
        
        #print("length is  > than count")
        #print(count)
        if count < len(userIDlist):
            params = tuple(userIDlist[count:count+100])
            #print("this should happen")

        else:        
            params = tuple(userIDlist)
        try:
            count += 100
            #print("Entering try for get response")
            #print(params)
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
            #print(response.text.encode("utf-8"))
            data = response.json()
            userinfolist += data["data"]
    #print("checking")
    #for x in range(len(userinfolist)): 
    #    print(userinfolist[x]["login"])
    return userinfolist

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
        ('first', 100),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    totaldata = []

    runningtotal = 1000
    i = 0
    while i < runningtotal:
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
            #print(response.text.encode("utf-8"))
            data = response.json()
            i = i + 100
            #print("checking\n")
            #print(i)
            if len(data) != 0:
                if data["total"] < 200:
                    runningtotal = data["total"] 
                else:
                    runningtotal = 200
                
                if "cursor" in data["pagination"]:
                    pagination = data["pagination"]["cursor"]
                    params = (
                        ('from_id',userID),
                        ('first', 100),
                        ('after', pagination)
                    )
                totaldata += data['data']
            else:
                print("This error shouldn't happen")
    #print(len(totaldata))
    #for x in range(len(totaldata)): 
    #    print(totaldata[x])
    return totaldata

def getvideoID(userID, timestamp):
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
        ('user_id',userID),
        ('first', 100),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    
    try:
        response = requests.get('https://api.twitch.tv/helix/videos?', headers=headers, params=params)
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
