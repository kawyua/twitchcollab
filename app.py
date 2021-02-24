import re
import os
import csv
import json
import datetime
import requests
from flask import Flask, render_template, request, redirect, session,url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from datetime import timedelta
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
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
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPE = ''
ENV = os.getenv("ENV")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION")
FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
BASE_URL = 'https://api.twitch.tv/helix/'
http = sessions.BaseUrlSession(base_url="https://api.twitch.tv/helix")
http = requests.Session()


DEFAULT_TIMEOUT = 5 # seconds

class TimeoutHTTPAdapter(HTTPAdapter):
    '''
    sets up http adaptor for custom request settings
    '''
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
ADAPTER = TimeoutHTTPAdapter(timeout=2.5)
http.mount("https://", ADAPTER)
http.mount("http://", ADAPTER)
TOTAL = 3
STATUS_FORCELIST=[413, 429, 500, 502, 503, 504]
METHOD_WHITELIST=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
BACKOFF_FACTOR = 1

retries = Retry(total=TOTAL,
    backoff_factor=BACKOFF_FACTOR,
    status_forcelist=STATUS_FORCELIST,
    method_whitelist = METHOD_WHITELIST)
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
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

db = SQLAlchemy(app)

class Users(db.Model):
    """
    Stores user login history
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    def __init__(self, user_id, login, updated_at):
        self.user_id = user_id
        self.login = login
        self.updated_at = updated_at

class Callhistory(db.Model):
    '''
    stores the calls a user calls, anon has user_id = 0 and login = ""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    login = db.Column(db.String(32))
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    "id":"int",
    "login":"string",
    "display_name":"string",
    "type":"",
    "broadcaster_type": null or "partner",
    "description":"string","profile_image_url":"url",
    "offline_image_url":"url",
    "view_count":int,
    "created_at":"datetime of '%Y-%m-%dT%H:%M:%SZ"}
    '''
    __tablename__ = 'callhistory'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    to_id = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime)
    def __init__(self, user_id, to_id, updated_at):
        self.user_id = user_id
        self.to_id = to_id
        self.updated_at = updated_at

class Callsaved(db.Model):
    '''
    Save calls from a user 
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    login = db.Column(db.String(32))
    to_login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'callsaved'
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer)
    from_login = db.Column(db.String(32))
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(32))
    updated_at = db.Column(db.DateTime)
    def __init__(self, from_id, from_login, to_id, to_login, updated_at):
        self.from_id = from_id
        self.from_login = from_login
        self.to_id = to_id
        self.to_login = to_login
        self.updated_at = updated_at

class Followcache(db.Model):
    '''
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer)
    from_login = db.Column(db.String(200), unique=True)
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    followed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'followcache'
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer)
    from_login = db.Column(db.Unicode(100))
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.Unicode(100))
    followed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    def __init__(self, from_id, from_login, to_id, to_login, followed_at, updated_at):
        self.from_id = from_id
        self.from_login = from_login
        self.to_id = to_id
        self.to_login = to_login
        self.followed_at = followed_at
        self.updated_at = updated_at

@app.route('/')
def index():
    '''
    / is the default page, sends people to redirect, people can deny
    '''
    print("scope print")
    print(SCOPE)
    if not validateaccesstoken():
        return redirect(
            'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
        .format(CLIENT_ID, REDIRECT_URI, SCOPE))
    else:
        isindex = True
        return render_template('index.html', isIndex = isindex)

def getanon():
    '''
    For people that do not login through their twitch,
    '''
    url ='https://id.twitch.tv/oauth2/token' 
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
        session['access_token'] =  response.json()[u'access_token']
        print(response.json())
        headers = {
            'client-id': CLIENT_ID,
            'Authorization': 'Bearer {0}'.format(session['access_token']),
        }
        #print("checking user")
        params = (
        )
        url = 'https://id.twitch.tv/oauth2/validate?'
        data2 = getrequest(url,headers, params)
        
        if len(data2) > 0:
            user_id = 0
            login = ""
            updated_at = datetime.datetime.utcnow()
            userdata = Users(user_id, login, updated_at)
            db.session.add(userdata)
            db.session.commit()
    return

def validateaccesstoken():
    '''
     checks if access token is valid, if none in session go anon
     returns boolean where if not valid and no refresh token in session, noredirect is false
    '''
    noredirect = True
    print(CLIENT_ID)
    session["client_id"] = CLIENT_ID
    session["redirect_uri"] = REDIRECT_URI
    if 'access_token' in session:
        headers = {
            'client-id': CLIENT_ID,
            'Authorization': 'Bearer {0}'.format(session['access_token']),
        }
        #print("checking user")
        params = (
        )
        url = 'https://id.twitch.tv/oauth2/validate?'
        data = getrequest(url,headers, params)
        print(data)
        if "login" in data and "user_id" in data:
            if len(data) > 0:
                session["login"] =  data['login']
                session["user_id"] =  data['user_id']
                user_id = data['user_id']
                login = data['login']
                updated_at = datetime.datetime.utcnow()
                userdata = Users(user_id, login, updated_at)
                db.session.add(userdata)
                db.session.commit()
                rows = db.session.execute(
                        text('''SELECT from_id, to_login, to_id
                        FROM Callsaved
                        WHERE from_id = :session_user; ''' ),
                        {"session_user":int(session["user_id"])}
                )
                saved_users = []
                for row in rows:
                    print(row)
                    saved_users.append((row.to_login,row.to_id))
                session["saved_users"] = saved_users
                print(saved_users)
        elif "refresh_token" in session:
            noredirect = False
        else:
            getanon()
    else:
        getanon()
    return noredirect

@app.route("/login", methods=['GET'])
def login():
    '''sets access token for a twitch login
    returns {"access_token":"string","expires_in":5290773,"token_type":"bearer"} for anon
    {'access_token': 'os6qpanorsoebjy6dn5cq5fc5azab2', 'expires_in': 14801, 
    'refresh_token': 'sfjh8uwo2zav76a97werjubquy11pbat2e4ve12q03uw8gzx12', 
    'scope': ['user_read'], 'token_type': 'bearer'} for logged in
    '''
    url ='https://id.twitch.tv/oauth2/token' 
    code = request.args.get('code', None)
    scope = request.args.get('scope', None)
    print("printing scope:"+scope)
    if code:
        try:
            response = http.post(url, 
        data={'client_id':CLIENT_ID,
        'client_secret':CILENT_SECRET,
        'code':code,
        'grant_type':'authorization_code',
        'redirect_uri':REDIRECT_URI
        })

            # If the response was successful, no Exception will be raised
            response.raise_for_status()
        except HTTPError as http_err:
            print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            return redirect(url_for('index'))

        except Exception as err:
            print('Other error occurred: {0}'.format(err))  # Python 3.6
            return redirect(url_for('index'))
        else:
            data = response.json()
            print("logging in")
            print(data)
            session['access_token'] = data["access_token"]
            session['refresh_token'] = data["refresh_token"]

            if not validateaccesstoken():
                print("redirect to login if it doesn't work")
                return redirect(
                    'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
                    .format(CLIENT_ID, REDIRECT_URI, SCOPE))
            else:
                print("redirect to index")
                return redirect(url_for('index'))
    else:
        print("redirect to index due to no code or scope")
        return redirect(url_for('index'))

def insertfollows2(user_id):
    '''
    inserts follows of deepness 2
    '''
    print("inserting followdata")
    #delete and add followers of this user_id
    db.session.execute(
        text('DELETE FROM Followcache WHERE from_id = :user_id '),
        {"user_id":int(user_id)})
    followdata2 = insertfollows(user_id)
    
    #get all id that I don't have followdata of yet
    rs = db.session.execute(
            text('''SELECT t1.to_id 
            FROM Followcache t1 
            LEFT JOIN Followcache t2 ON t2.from_id = t1.to_id 
            WHERE t1.from_id = :user_id  AND t2.from_id IS NULL '''),
            {"user_id":int(user_id)})

    #insert all new user_id
    for row in rs:
        insertfollows(row.to_id)
    db.session.commit()

    #insert history
    timenow = datetime.datetime.utcnow()
    if "user_id" in session:
        from_id = session["user_id"]
        to_id = user_id
        dbdata = Callhistory(from_id, to_id, timenow)
        db.session.add(dbdata)
        db.session.commit()
    return followdata2

@app.route('/graph', methods=['GET'])
def graph():
    '''
    post from submission, sets the page for /submit and gets graph
    Returns: /submit template page
    '''
    if request.method == 'GET':
        if validateaccesstoken():
            login = request.args.get("login")
            if str(login) == '':
                print("empty user")
                return render_template('index.html', message='Please enter required fields')
            login = str(login)
            userdata = getuser(login)
            if len(userdata) == 0:
                return render_template('index.html', message='User doesnt exist.')
            #print("entering graphdata")
            graphdata = datatograph(userdata[0]["id"])
            graphdata["users"].append(userdata[0])
            firstfollow = datetime.datetime.strptime(graphdata["follows"][len(graphdata["follows"]) - 1]["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            graphdata = json.dumps(graphdata)
            now = datetime.datetime.utcnow()
            return render_template('graph.html',
                graphdata = graphdata,
                total = (now - firstfollow).total_seconds(),
                login = login
            )
        else:
            return redirect(
                'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
            .format(CLIENT_ID, REDIRECT_URI, SCOPE))

    else:
        return'Bad Request', 400

@app.route('/history',methods = ['POST', 'GET'])
def history():
    '''
    post from submission, sets the page for /submit and gets graph
    Returns: /submit template page
    '''
    if request.method == 'GET':
        if validateaccesstoken():
            login = request.args.get("login")
            if str(login) == '':
                print("empty user")
                return render_template('index.html', message='Please enter required fields')
            login = str(login)
            userdata = getuser(login)
            if len(userdata) == 0:
                return render_template('index.html', message='User doesnt exist.')
            print("entering followdata")
            date_time_obj = datetime.datetime.strptime((userdata[0]["created_at"]), '%Y-%m-%dT%H:%M:%S.%fZ')
            print(date_time_obj)
            #remember followdata is already sorted by most recent follow date
            timenow = datetime.datetime.utcnow() - timedelta(days=7)
            userid = userdata[0]["id"]
            followdata2 = getfollowdata(userid)
            userlist = []
            for follower in followdata2["data"]:
                userlist.append(('id',follower["to_id"]))
                follower["followed_at"] = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        
            followcomparison = addvideoinfo(followdata2)
            print("entering getmultiuserinfo function")
            multiuserinfo = getMultiUserInfo(userlist)
            print("leaving getmultiuserinfo function")
            #sorts multiuserinfo by follow date
            object_map = {o['id']: o for o in multiuserinfo}
            multiuserinfo = []
            for id in followdata2["data"]:
                if id["to_id"] in object_map:
                    multiuserinfo.append(object_map[id["to_id"]])
            totalfollows = followdata2["total"]
            print("leaving follow")
            return render_template('follow.html',
                data = multiuserinfo,
                followdata = followcomparison,
                followlen = totalfollows,
                userdata=userdata)
        else:
            return redirect(
                'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
            .format(CLIENT_ID, REDIRECT_URI, SCOPE))
    else:
        return'Bad Request', 400

@app.route('/adduser', methods=['POST'])
def adduser():
    '''
    from submission, checks and adds users to their save history
    Returns: 'success' if it works
    '''
    print("entering adduser")
    if request.method == 'POST' and "user_id" in session:
        login = request.form['login']
        user_id = request.form['user_id']
        print(login)
        print(user_id)
        #check if already in database
        
        rows = db.session.execute(
                text('''SELECT COUNT(*) AS total
                FROM Callsaved
                WHERE from_id = :session_user 
                AND to_id = :user_id; ''' ),
                {"session_user":int(session["user_id"]),"user_id":int(user_id)}
        )
        total = 5
        from_id = 0
        for row in rows:
            total = row.total
        print(total)
        print(from_id)
        if total == 0:
            #insert history
            timenow = datetime.datetime.utcnow()
            from_id = session["user_id"]
            from_login = session["login"]
            dbdata = Callsaved(from_id, from_login, user_id, login, timenow)
            db.session.add(dbdata)
            db.session.commit()
            print('saved')
            return 'Success'
        print('already have data')
        return 'Failure'
    else:
        return 'Failure'

@app.route('/deleteuser', methods=['POST'])
def deleteuser():
    '''
    from submission, checks and adds users to their save history
    Returns: 'success' if it works
    '''
    print("entering deleteuser")
    if request.method == 'POST' and "user_id" in session:
        login = request.form['login']
        user_id = request.form['user_id']
        print(login)
        print(user_id)
        #delete and add followers of this user_id
        
        db.session.execute(
            text('''DELETE
            FROM Callsaved
            WHERE from_id = :session_user 
            AND to_id = :user_id; ''' ),
            {"session_user":int(session["user_id"]),"user_id":int(user_id)}
        )
        total = 0
        #todo database verification
        db.session.commit()
        rows = db.session.execute(
                text('''SELECT COUNT(*) AS total
                FROM Callsaved
                WHERE from_id = :session_user 
                AND to_id = :user_id; ''' ),
                {"session_user":int(session["user_id"]),"user_id":int(user_id)}
        )
        total = 5
        from_id = 0
        for row in rows:
            total = row.total
        print(total)
        print(from_id)
        if total == 0:
            return 'Success'
        print('Failed deletion')
        return 'Failure'
    else:
        print('Failed deletion')
        return 'Failure'

@app.route('/gettriads', methods=['POST'])
def gettriads():
    '''
    from submission, sets the page for /submit and calls to make recommendations
    Returns: /submit template page
    '''
    if request.method == 'POST':
        
        if 'login' not in request.form:
            return render_template('index.html', message='Input is wrong')
        login = request.form['login']
        if login == '':
            #print("empty user")
            return render_template('index.html', message='Please enter required fields')
        userdata = getuser(login)
        print(login)
        print(userdata)
        if len(userdata) == 0:
            return render_template('index.html', message='User doesnt exist.')
        getfollows(userdata[0]["id"])
        
        return render_template('index.html')
    else:
        return'Bad Request', 400 

def insertfollows(user_id):
    '''
    parameter: user_id (Integer)
    inserts followdata for a user
    '''
    print("inserting new followers")
    print(user_id)
    followdata = getfollowers(user_id)
    timenow = datetime.datetime.utcnow()
    for follower in followdata["data"]:
        from_id = follower["from_id"]
        from_login = str(follower["from_login"])
        to_id = follower["to_id"]
        to_login = follower["to_login"]
        followed_at = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
        db.session.add(dbdata)
        db.session.commit()
    return followdata

def getfollowtotal(user_id):
    '''
    calls database to get the number of followers each streamer has
    '''
    followtotal = {}
    rows = db.session.execute(
            text('''SELECT A.to_id AS from_id, COUNT(B.to_id) AS total
            FROM Followcache A, Followcache B
            WHERE A.from_id = :user_id 
            AND A.to_id  = B.from_id 
            GROUP BY A.to_id; ''' ),
            {"user_id":int(user_id)})
    
    for row in rows:
        follow_id = str(row.from_id)
        if follow_id in followtotal:
            followtotal[follow_id].append(row.total)
        else:
            followtotal[follow_id] = row.total
    return followtotal

def getfollowdata(user_id):
    '''
    calls to get follows of a twitch user_id with common follows and triadic closures
    returns followdata json with additional info on each follow
    '''
    followdata = insertfollows2(user_id)
    commonfollowsession = {}
    familiarfollowers = {}
    triad = {}
    followtotal = getfollowtotal(user_id)

    firstfollow = datetime.datetime.strptime(followdata["data"][len(followdata["data"]) - 1]["followed_at"], '%Y-%m-%dT%H:%M:%SZ')

    if "user_id" in session and session["user_id"] != user_id :
        userselect = session["user_id"]
        insertfollows2(session["user_id"])
        #get common follows
        rows = db.session.execute(
                text('''SELECT A.to_login AS from_login, B.to_login AS to_login,
                A.to_id AS from_id, B.to_id AS to_id, A.followed_at AS followed_at_origin,
                B.followed_at AS followed_at_source 
                FROM Followcache A, Followcache B, Followcache C 
                WHERE A.from_id = :user_id AND C.from_id = :userselect 
                AND A.to_id  = B.from_id AND B.to_id = C.to_id ORDER BY A.followed_at DESC; '''),
                {"user_id":int(user_id) , "userselect":int(userselect)})
        
        print("checkcommonfollows")
        for row in rows:
            follow_id = str(row.from_id)
            if follow_id in commonfollowsession:
                commonfollowsession[follow_id].append((row.to_login,row.to_id))
            else:
                commonfollowsession[follow_id] = [(row.to_login,row.to_id)]
        #get common follows
        rows = db.session.execute(
                text('''SELECT A.to_login AS from_login, B.to_login AS to_login,
                A.to_id AS from_id, B.to_id AS to_id, A.followed_at AS followed_at_origin,
                B.followed_at AS followed_at_source 
                FROM Followcache A, Followcache B, Followcache C 
                WHERE A.from_id = :userselect AND C.from_id = :user_id 
                AND A.to_id  = B.from_id AND B.to_id = C.to_id ORDER BY A.followed_at DESC; '''),
                {"userselect":int(userselect) , "user_id":int(user_id)})
        print("checkcommonfollows2")
        for row in rows:
            follow_id = str(row.to_id)
            if follow_id in familiarfollowers:
                familiarfollowers[follow_id].append((row.from_login,row.to_id))
            else:
                familiarfollowers[follow_id] = [(row.from_login,row.to_id)]
    else:
        #get common follows for anon
        print("getting common follows anon")
        rows = db.session.execute(
                text('''SELECT A.to_login AS from_login, B.to_login AS to_login,
                A.to_id AS from_id, B.to_id AS to_id, A.followed_at AS followed_at_origin,
                B.followed_at AS followed_at_source 
                FROM Followcache A, Followcache B, Followcache C 
                WHERE A.from_id = :user_id AND C.from_id = :user_id AND A.to_id  = B.from_id 
                AND B.to_id = C.to_id ORDER BY A.followed_at DESC; '''),
                {"user_id":int(user_id)})
        for row in rows:
            follow_id = str(row.from_id)
            if follow_id in commonfollowsession:
                commonfollowsession[follow_id].append((row.to_login,row.to_id))
            else:
                commonfollowsession[follow_id]=[(row.to_login,row.to_id)]
    #get triads
    rows = db.session.execute(
            text('''SELECT A.to_login AS from_login, B.to_login AS to_login,
            A.to_id AS from_id, B.to_id AS to_id, C.to_id AS origin_id,
            A.followed_at AS followed_at_origin, B.followed_at AS followed_at_source 
            FROM Followcache A, Followcache B, Followcache C 
            WHERE A.from_id = :user_id AND C.from_id = :user_id  
            AND A.to_id  = B.from_id AND B.to_id = C.to_id 
            AND A.followed_at < C.followed_at AND B.followed_at < C.followed_at ; ''' ),
            {"user_id":int(user_id)})
    print("getting triad")
    for row in rows:
        follow_id = str(row.to_id)
        followtime = 0
        if (row.followed_at_source - firstfollow).total_seconds() > 0:
            #gets follow time compared to first follow
            followtime = (row.followed_at_source - firstfollow).total_seconds()
        else: #default to user followdate for the time compared to first follow
            followtime = 0
        if follow_id in triad:
            triad[follow_id].append((row.from_login, row.from_id, followtime))
        else:
            triad[follow_id]=[(row.from_login, row.from_id, followtime)]

    for index, follow in enumerate(followdata["data"]):
        followdata["data"][index]["commonfollowsession"] = []
        followdata["data"][index]["familiarfollowers"] = []
        followdata["data"][index]["triad"] = []
        followdata["data"][index]["followtotal"] = []
        follow_id = str(follow["to_id"])
        if follow_id in commonfollowsession:
            followdata["data"][index]["commonfollowsession"] += commonfollowsession[follow_id]
        if follow_id in triad:
            followdata["data"][index]["triad"] += triad[follow_id]
        if follow_id in familiarfollowers:
            followdata["data"][index]["familiarfollowers"] += familiarfollowers[follow_id]
        if follow_id in followtotal:
            followdata["data"][index]["followtotal"] = followtotal[follow_id]
        followdata["data"][index]["followtime"] = (
            datetime.datetime.strptime(followdata["data"][index]["followed_at"], '%Y-%m-%dT%H:%M:%SZ') - firstfollow).total_seconds()
    return followdata

def datatograph(user_id):
    '''
    parameter: user_id

    returns graphout = {"users":multiuserinfo , "follows":followdata}
    '''
    graphoutput = {}
    followerslist = getfollowdata(user_id)["data"]
    userlist = []
    for follow in followerslist:
        userlist.append(('id',follow["to_id"]))
    multiuserinfo = getMultiUserInfo(userlist)

    ##print("entering getmultiuserinfo function")
    graphoutput["users"] = multiuserinfo
    graphoutput["follows"] = followerslist
    return graphoutput

def addvideoinfo(followdata):
    '''
    calls getvideo_id and adds video_id, video_timestamp, video_info to followdata
    '''
    
    expiredate = datetime.datetime.utcnow() - datetime.timedelta(60)
    for index,twitchuser in enumerate(followdata["data"]):
        if twitchuser["followed_at"] > expiredate:
            videoinfo = getvideoID(twitchuser["to_id"], twitchuser["followed_at"])
            if videoinfo is not None:
                followdata["data"][index]["video_id"] = videoinfo[0]
                followdata["data"][index]["video_timestamp"] = videoinfo[1]
                followdata["data"][index]["video_info"] = videoinfo[2]
    return followdata["data"]

def getuser(username):
    '''
    Calls twitch api to get information of a specific username:
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
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    params = (
        ('login',username),
    )
    url = 'https://api.twitch.tv/helix/users?'
    data = getrequest(url, headers, params)["data"]
    return data

def getMultiUserInfo(userlist):
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
    #print(str(userlist))
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/users?'
    count = 0
    userinfolist = []
    #print("entering getmultiuserinfo while loop")
    while len(userlist) > count:
        if count < len(userlist):
            params = tuple(userlist[count:count+100])

        else:
            params = tuple(userlist)
        count += 100
        userinfolist += getrequest(url, headers, params)["data"]
    return userinfolist

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
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/users/follows?'
    data = getrequest(url, headers, params)
    return data

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
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/users/follows?'
    data = getrequest(url, headers, params)
    return data["data"]

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
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/users/follows?'
    totaldata = getrequest(url, headers, params)["data"]

    csv_columns = ['from_id', 'from_login', 'from_name',
        'to_id', 'to_login','to_name','followed_at']
    csv_file = "Names.csv"
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in totaldata:
                writer.writerow(data)
    except IOError:
        print("I/O error")
    streamerfollowdata = getfollowers(userID)["data"]
    streamerfollowset = {}
    for streameruser in streamerfollowdata:
        date_time_streameruser = datetime.datetime.strptime(
            streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        streamerfollowset.setdefault(streameruser["to_name"] , date_time_streameruser)
    csv_columns2 = ['from_id', 'from_login', 'from_name', 'to_id', 'to_login',
    'to_name','followed_at','closure','follow_total','triad_set', 'k-connected','total-connected']
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
        twitchuserfollows = getfollowers(twitchuser["from_id"])["data"]
        print(str(index) + "getting triadic closure")
        eachfollowdata = gettriadicclosure(twitchuser, twitchuserfollows)
        print(str(index) + "completed getting triadic closure")
        twitchuserfollowset = {}
        for streameruser in twitchuserfollows:
            date_time_streameruser = datetime.datetime.strptime(
                streameruser["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            twitchuserfollowset.setdefault(streameruser["to_name"] , date_time_streameruser)
        eachfollowdata["k-connected"] = list(set(streamerfollowset.keys()) 
        & set(twitchuserfollowset.keys()))
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
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/videos?'
    videodata = getrequest(url, headers, params)["data"]
    returninfo = ""
    for video in videodata:
        if datetime.datetime.strptime(video["created_at"], '%Y-%m-%dT%H:%M:%SZ') < timestamp:
            total = (timestamp - datetime.datetime.strptime(video["created_at"], '%Y-%m-%dT%H:%M:%SZ')).total_seconds()
            hours = total // 3600
            total = total - (hours * 3600)
            minutes = total // 60
            seconds = total - (minutes * 60)
            returntime = '{:02d}h{:02d}m{:02d}s'.format(int(hours), int(minutes), int(seconds))
            duration = re.split("\D", video["duration"])
            total_duration = 0
            if duration and len(duration) == 4:
                total_duration = int(duration[0])*3600+int(duration[1])*60+int(duration[2])
            elif duration and len(duration) == 3:
                total_duration = int(duration[0])*60+int(duration[1])
            elif duration and len(duration) == 2:
                total_duration = int(duration[1])
            if total > total_duration:
                returninfo = "Followed When Not Live"
            elif video["viewable"] != "public":
                returninfo = "Broadcast is not public"
            else:
                returninfo = video["title"]
            return [video["id"], returntime, returninfo]

def getrequest(url, headers, params, pagination = 1000):
    '''
    pagination default is 1000
    '''
    parameter = params
    header = headers
    totaldata = {"data":[]}
    print(params)

    i = 0
    while i < pagination:
        try:
            response = http.get(url, headers=header, params=parameter)
            # If the response was successful, no Exception will be raised
            response.raise_for_status()
        except HTTPError as http_err:
            print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            #refresh()
            #getrequest(url, headers, params)
            return "unsuccessful"
        except Exception as err:
            print('Other error occurred: {0}'.format(err))  # Python 3.6
            return "unsuccessful"
        else:
            data = response.json()
            #print(data)
            i = i + 100
            #print("checking\n")
            #print(i)
            if len(data) != 0 and "pagination" in data:
                if "total" in data and data["total"] < pagination:
                    totaldata["total"] = data["total"]
                    pagination = data["total"] 
                elif "total" in data and data["total"] > pagination:
                    totaldata["total"] = data["total"]
                    print("warning over pagination limit")
                
                if "cursor" in data["pagination"]:
                    paginate = data["pagination"]["cursor"]
                    parameter = params + (('after', paginate),)
                else:
                    i = pagination
                totaldata["data"] += data['data']
            else:
                totaldata = data
                i = pagination
    return totaldata

if __name__ == '__main__':
    app.run()
   # testmode(ENVIRONMENT)
