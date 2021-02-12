from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
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
import re
import csv
import ast


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
    print("getting access_token")
    response = http.post(url, 
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



class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    def __init__(self, user_id, login, updated_at):
        self.user_id = user_id
        self.login = login
        self.updated_at = updated_at

class Followcache(db.Model):
    '''
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer)
    from_login = db.Column(db.String(200), unique=True)
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    followed_at = db.Column(db.DateTime)
    triad_set = db.Column(db.Text)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'followcache'
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer)
    from_login = db.Column(db.Unicode(100))
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.Unicode(100))
    followed_at = db.Column(db.DateTime)
    triad_set = db.Column(db.Text)
    updated_at = db.Column(db.DateTime)
    def __init__(self, from_id, from_login, to_id, to_login, followed_at, triad_set, updated_at):
        self.from_id = from_id
        self.from_login = from_login
        self.to_id = to_id
        self.to_login = to_login
        self.followed_at = followed_at
        self.triad_set = triad_set
        self.updated_at = updated_at


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
            return render_template('index.html', message='Input is wrong')
        #print(request.form['login'])
        login = request.form['login']
        if login == '':
            #print("empty user")
            return render_template('index.html', message='Please enter required fields')
        userdata = getuser(login)
        print(login)
        print(userdata)
        if len(userdata["data"]) == 0:
            return render_template('index.html', message='User doesnt exist.')
        print("entering graphdata")
        graphdata = datatograph(userdata["data"][0]["id"])
        graphdata["users"].append(userdata["data"][0])
        graphdata = json.dumps(graphdata)
        return render_template('graph.html', 
            graphdata = graphdata
        )
    else:
        return'Bad Request', 400 

@app.route('/gettriads', methods=['POST'])
def gettriads():
    '''
    from submission, sets the page for /submit and calls to make recommendations
    Parameters in post: twitchuser
    Returns: /submit template page
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
        print(login)
        print(userdata)
        if len(userdata["data"]) == 0:
            return render_template('index.html', message='User doesnt exist.')
        getfollows(userdata["data"][0]["id"])

        return render_template('index.html')
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
        #remember followdata is already sorted by most recent follow date
        timenow = datetime.datetime.utcnow() - timedelta(days=7)
        userid = userdata["data"][0]["id"]
        # & Followcache.updated_at - timenow < delta
        followdata = getfollowers(userdata["data"][0]["id"])
        #
        userfollowset = []
        for streamuser in followdata:
            userfollowset.append(streamuser["to_name"])
        rs = db.session.execute(
             text('SELECT * FROM Followcache WHERE from_id = :userid AND updated_at > :timenow ORDER BY updated_at ASC '),
             {"userid":int(userid), "timenow":timenow })
        newfollowdata = followcompare(userfollowset, followdata)
        #if rs.rowcount > 0:
        #    newfollowdata = followcompare(userfollowset, followdata)
        #else:
        #    newfollowdata = []
        #    #y = ast.literal_eval(x)
        #    for row in rs:
        #        newfollowdata.append({'from_id':row.from_id, 'from_login':row.from_login, 'to_id':row.to_id, 'to_login':row.to_login, 'followed_at':row.followed_at, 'triad_set':row.triad_set})
        followcomparison = addvideoinfo(newfollowdata)

        userIDlist = []
        for follow in followdata:
            userIDlist.append(('id',follow["to_id"]))
            
        #print("entering getmultiuserinfo function")
        multiuserinfo = getMultiUserInfo(userIDlist)
        #sorts multiuserinfo by follow date
        object_map = {o['id']: o for o in multiuserinfo}
        multiuserinfo = [object_map[id["to_id"]] for id in followdata]
        totalfollows = len(followdata)

        return render_template('follow.html',
            data = multiuserinfo, 
            followdata = followcomparison,
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
    #print("entering data")
    graphoutput = {}
    followerslist = getfollowers(id)
    
    userIDlist = []
    for follow in followerslist:
        userIDlist.append(('id',follow["to_id"]))
    #print("entering getmultiuserinfo function")
    multiuserinfo = getMultiUserInfo(userIDlist)
    graphoutput["users"] = multiuserinfo
    graphoutput["follows"] = followerslist
    #print(str(graphoutput))
    return graphoutput

def followcompare(userdata, followdata):
    '''
    Makes a comparison. followed at and follow recency to modify search values.
    Parameters: a user id
    Returns:  {'from_id': '49886567', 'from_login': 'kawyua', 'from_name': 'kawyua', 'to_id': '552120296', 'to_login': 'zackrawrr', 'to_name': 'zackrawrr', 
    'followed_at': '2021-01-09T09:53:59Z', 'follow_match': [], 'follow_total': 1}
    '''
    followdatalength = len(followdata)
    if followdatalength > 0:
        originfollows = {}
        triadset = {}
        updated_at = datetime.datetime.utcnow()

        for twitchuser in followdata:
            date_time_twitchuser = datetime.datetime.strptime(twitchuser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            originfollows.setdefault(twitchuser["to_name"], date_time_twitchuser)
        
        #enumerate in reverse in order to properly get triad calls
        for index,twitchuser in enumerate(reversed(followdata)):
            streamerfollows = getfollowers(twitchuser["to_id"])
            streamfollowset = {}
            for streameruser in streamerfollows:
                date_time_streameruser = datetime.datetime.strptime(streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
                streamfollowset.setdefault(streameruser["to_name"] , date_time_streameruser)
            #followrecency = (currDate - date_time_obj)
            #gets matches with search origin
            followdata[followdatalength - index - 1]["origin_match"] = list(set(originfollows.keys()) & set(streamfollowset.keys()))
            #todo this will eventually be different from origin match when login is implemented
            followdata[followdatalength - index - 1]["follow_match"] = list(set(userdata) & set(streamfollowset.keys()))
            followdata[followdatalength - index - 1]["follow_total"] = len(streamerfollows)
            followdata[followdatalength - index - 1]["triad_set"] = []
            #print(triadset)
            usertriadset = triadset.get(twitchuser["to_name"])
            #print("nowusertriadset for" + twitchuser["to_name"])
            #print(usertriadset)
            if usertriadset:
                #print("followed" + twitchuser["to_name"])
                for triad in usertriadset:
                    if usertriadset[triad] < originfollows[triad]:
                        #print(triad + "followed is a triad to" + twitchuser["to_name"])
                        followdata[followdatalength - index - 1]["triad_set"].append(triad)
            potentialtriadset = twitchuser["origin_match"]
            #print("printingorigin" + str(twitchuser["origin_match"]))
            if potentialtriadset: #if not empty
                for triad in potentialtriadset: #iterate through each
                    #print("printing triad" + triad)
                    triadset.setdefault(triad,{})
                    triadset[triad][twitchuser["to_name"]] = streamfollowset[triad]
            #print("for user" + followdata[followdatalength - index - 1]["to_name"])
            #Sprint(followdata[followdatalength - index - 1]["triad_set"])
            streamfollowset.clear()
            from_id = followdata[followdatalength - index - 1]["from_id"]
            from_login = str(followdata[followdatalength - index - 1]["from_login"])
            to_id = followdata[followdatalength - index - 1]["to_id"]
            to_login = str(followdata[followdatalength - index - 1]["to_login"])
            followed_at = followdata[followdatalength - index - 1]["followed_at"]
            triad_set = str(followdata[followdatalength - index - 1]["triad_set"])
            
            dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, triad_set,updated_at)
            db.session.add(dbdata)
            #print(followdata)
            db.session.commit()
    
    return followdata

def addvideoinfo(followdata):
    for index,twitchuser in enumerate(followdata):
        videoinfo = getvideoID(twitchuser["to_id"], twitchuser["followed_at"])
        if videoinfo is not None:
            followdata[index]["video_id"] = videoinfo[0]
            followdata[index]["video_timestamp"] = videoinfo[1]
            followdata[index]["video_info"] = videoinfo[2]
    return followdata

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
        response = http.get('https://api.twitch.tv/helix/users?', headers=headers, params=params)

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
        user_id = data["data"][0]["id"]
        login = username
        updated_at = datetime.datetime.utcnow()
        userdata = Users(user_id, login, updated_at)
        db.session.add(userdata)
        db.session.commit()
        return data

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
            response = http.get('https://api.twitch.tv/helix/users?', headers=headers, params=params)

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
            print("Ratelimit -Limit" + response.headers['Ratelimit-Limit'])
            print("Ratelimit -Remaining" + response.headers['Ratelimit-Remaining'])
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

    runningtotal = 500
    i = 0
    while i < runningtotal:
        try:
            response = http.get('https://api.twitch.tv/helix/users/follows?', headers=headers, params=params)
            # If the response was successful, no Exception will be raised
            response.raise_for_status()
        except HTTPError as http_err:
            #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
        except Exception as err:
            #print('Other error occurred: {0}'.format(err))  # Python 3.6
            return render_template('index.html', message='Other error occurred: {0}'.format(err))
        else:
            data = response.json()
            i = i + 100
            #print("checking\n")
            #print(i)
            if len(data) != 0:
                if data["total"] < 500:
                    runningtotal = data["total"] 
                else:
                    runningtotal = 500
                
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
    #print("Ratelimit -Limit" + response.headers['Ratelimit-Limit'])
    #print("Ratelimit -Remaining" + response.headers['Ratelimit-Remaining'])
    return totaldata

def getspecificfollows(fromuserID, touserID):
    '''
    Calls twitch api to get followers of a specific userid:
    Parameters: fromuserID, touserID
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
        ('from_id',fromuserID),
        ('to_id', touserID),
        ('first', 1),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    try:
        response = http.get('https://api.twitch.tv/helix/users/follows?', headers=headers, params=params)
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
        if len(data) != 0:
            data = data['data']
        #print("checking\n")
        #print(i)
    #print(len(totaldata))
    #for x in range(len(totaldata)): 
    #    print(totaldata[x])
    #print("Ratelimit -Limit" + response.headers['Ratelimit-Limit'])
    #print("Ratelimit -Remaining" + response.headers['Ratelimit-Remaining'])
    return data

def getfollows(userID):
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
        ('to_id',userID),
        ('first', 100),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    totaldata = []

    runningtotal = 500
    i = 0
    print("entering getfollowrequest" + userID)
    while i < runningtotal:
        try:
            response = http.get('https://api.twitch.tv/helix/users/follows?', headers=headers, params=params)
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
                if data["total"] < 500:
                    runningtotal = data["total"] 
                else:
                    runningtotal = 500
                
                if "cursor" in data["pagination"]:
                    pagination = data["pagination"]["cursor"]
                    params = (
                        ('to_id',userID),
                        ('first', 100),
                        ('after', pagination)
                    )
                totaldata += data['data']
            else:
                print("This error shouldn't happen")
    #print("totaldata")
    #print(totaldata)
    #print(len(totaldata))
    #for x in range(len(totaldata)): 
    #    print(totaldata[x])
    csv_columns = ['from_id', 'from_login', 'from_name', 'to_id', 'to_login','to_name','followed_at']
    csv_file = "Names.csv"
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in totaldata:
                writer.writerow(data)
    except IOError:
        print("I/O error")
        
    streamerfollowdata = getfollowers(userID)
    streamerfollowset = {}
    for streameruser in streamerfollowdata:
        date_time_streameruser = datetime.datetime.strptime(streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        streamerfollowset.setdefault(streameruser["to_name"] , date_time_streameruser)
    csv_columns2 = ['from_id', 'from_login', 'from_name', 'to_id', 'to_login','to_name','followed_at','closure','follow_total','triad_set', 'k-connected','total-connected']
    csv_file2 = "Names2.csv"
    
    try:
        openfile = open(csv_file2, 'w', newline='', encoding='utf-8') 
        writer = csv.DictWriter(openfile, fieldnames=csv_columns2)
        writer.writeheader()
        openfile.close()
    except IOError:
        print("I/O error")

    print("entering getting follows for each follower")
    for index, twitchuser in enumerate(totaldata):
        print(getspecificfollows(twitchuser["from_id"],twitchuser["to_id"]))
        print(index)
        twitchuserfollows = getfollowers(twitchuser["from_id"])
        print(str(index) + "getting triadic closure")
        eachfollowdata = gettriadicclosure(twitchuser, twitchuserfollows)
        print(str(index) + "completed getting triadic closure")
        twitchuserfollowset = {}
        for streameruser in twitchuserfollows:
            date_time_streameruser = datetime.datetime.strptime(streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            twitchuserfollowset.setdefault(streameruser["to_name"] , date_time_streameruser)
        eachfollowdata["k-connected"] = list(set(streamerfollowset.keys()) & set(twitchuserfollowset.keys()))
        eachfollowdata["total-connected"] = len(eachfollowdata["k-connected"])
        print(eachfollowdata)
        try:
            with open(csv_file2, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns2)
                writer.writerow(eachfollowdata)
                csvfile.close()
        except IOError:
            print("I/O error")
    return 

def gettriadicclosure(userfollowdata, twitchuserfollows):
    '''
    Makes a comparison. followed at and follow recency to modify search values.
    Parameters: a user id
    Returns:  {'from_id': '49886567', 'from_login': 'kawyua', 'from_name': 'kawyua', 'to_id': '552120296', 'to_login': 'zackrawrr', 'to_name': 'zackrawrr', 
    'followed_at': '2021-01-09T09:53:59Z', 'follow_match': [], 'follow_total': 1}
    '''
    
    followdatalength = len(twitchuserfollows)
    if followdatalength > 0:
        date_time_user = datetime.datetime.strptime(userfollowdata["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        originfollows = {userfollowdata["from_name"]:date_time_user}
        triadset = {}
        userfollowdata["closure"] = 0
        userfollowdata["follow_total"] = followdatalength
        
        #enumerate in reverse in order to properly get triad calls
        for twitchuser in reversed(twitchuserfollows):
            streamerfollows = getspecificfollows(twitchuser["to_id"], userfollowdata["to_id"])
            if streamerfollows:
                date_time_streameruser = datetime.datetime.strptime(streamerfollows[0]["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
                triadset.setdefault(streamerfollows[0]["from_login"], date_time_streameruser)
            #followrecency = (currDate - date_time_obj)
            #gets matches with search origin
            #print(triadset)
            #print("nowusertriadset for" + twitchuser["to_name"])
            #print(usertriadset)
            #if 
            if twitchuser["to_name"] == userfollowdata["to_name"]:
                userfollowdata["triad_set"] = []
                print(userfollowdata["from_name"] + "followed" + twitchuser["to_name"])
                print(triadset)
                for triad in triadset:
                    if triadset[triad] < originfollows[userfollowdata["from_login"]]:
                        userfollowdata["triad_set"].append(triad)
                        userfollowdata["closure"] = 1
                return userfollowdata
        print("error occurred when getting follows, user has too many follows")
        userfollowdata["triad_set"] = []
        return userfollowdata


def getvideoID(userID, timestamp):
    '''
    Calls twitch api to get followers of a specific userid:
    Parameters: a user id
    api call Returns: A json list of structure 
    {
    "data": [{
        "id": "234482848",
        "user_id": "67955580",
        "user_login": "chewiemelodies",
        "user_name": "ChewieMelodies",
        "title": "-",
        "description": "",
        "created_at": "2018-03-02T20:53:41Z",
        "published_at": "2018-03-02T20:53:41Z",
        "url": "https://www.twitch.tv/videos/234482848",
        "thumbnail_url": "https://static-cdn.jtvnw.net/s3_vods/bebc8cba2926d1967418_chewiemelodies_27786761696_805342775/thumb/thumb0-%{width}x%{height}.jpg",
        "viewable": "public",
        "view_count": 142,
        "language": "en",
        "type": "archive",
        "duration": "3h8m33s"
    }],
    "pagination":{"cursor":"eyJiIjpudWxsLCJhIjoiMTUwMzQ0MTc3NjQyNDQyMjAwMCJ9"}
    }
    '''
    params = (
        ('user_id',userID),
        ('first', 100),
        ('type', "archive"),
    )
    
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    #now = datetime.datetime.utcnow()
    timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
    #print((now - timestamp).days)
    #if (now - timestamp) < datetime.timedelta(days=60):
    try:
        response = http.get('https://api.twitch.tv/helix/videos?', headers=headers, params=params)
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        #print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(http_err))
    except Exception as err:
        #print('Other error occurred: {0}'.format(err))  # Python 3.6
        return render_template('index.html', message='Other error occurred: {0}'.format(err))
    else:
        videodata = response.json()
        returnInfo = ""
        for video in videodata['data']:
            if datetime.datetime.strptime(video["created_at"], '%Y-%m-%dT%H:%M:%SZ') < timestamp:
                total = (timestamp - datetime.datetime.strptime(video["created_at"], '%Y-%m-%dT%H:%M:%SZ')).total_seconds()
                hours = total // 3600
                total = total - (hours * 3600)
                minutes = total // 60
                seconds = total - (minutes * 60)
                datetime.datetime.strptime(video["created_at"], '%Y-%m-%dT%H:%M:%SZ')
                returnTime = '{:02d}h{:02d}m{:02d}s'.format(int(hours), int(minutes), int(seconds))
                duration = re.split("\D", video["duration"])
                total_duration = int(duration[0])*3600+int(duration[1])*60+int(duration[2])
                if total > total_duration:
                    returnInfo = "Followed When Not Live"
                elif video["viewable"] != "public":
                    returnInfo = "Broadcast is not public"
                else:
                    returnInfo = video["title"]
                return [video["id"], returnTime, returnInfo]
       



if __name__ == '__main__':
    app.run()
   # testmode(ENVIRONMENT)
