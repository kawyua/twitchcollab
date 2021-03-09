import os
import csv
import json
import datetime
import requests
import html
from flask import Flask, render_template, request, redirect, session,url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from datetime import timedelta
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import redis
from rq import Queue
from rq.job import Job
from worker import conn
import urllib.request

from functions import (postrequest, getrequest, getvideoID,
getfollowers, getMultiUserInfo, getuser, addvideoinfo, getallfollows, get_app_access_token_header)

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

q = Queue(connection=conn)
print(conn)

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

class SavedFollows(db.Model):
    '''
    id = db.Column(db.Integer, primary_key=True)
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'savedfollows'
    id = db.Column(db.Integer, primary_key=True)
    to_id = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime)
    def __init__(self, to_id, updated_at):
        self.to_id = to_id
        self.updated_at = updated_at

@app.route('/')
def index():
    '''
    / is the default page, sends people to redirect, people can deny
    '''
    print("scope print")
    print(SCOPE)
    if not validate_access_token():
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
    data={'client_id':CLIENT_ID,
        'client_secret':CILENT_SECRET,
        'grant_type':'client_credentials'
        }
    response = postrequest(url, data)
    session['access_token'] =  response['access_token']
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

def validate_access_token():
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
    code = request.args.get('code', None)
    scope = request.args.get('scope', None)
    url ='https://id.twitch.tv/oauth2/token'
    data={'client_id':CLIENT_ID,
        'client_secret':CILENT_SECRET,
        'code':code,
        'grant_type':'authorization_code',
        'redirect_uri':REDIRECT_URI
        }
    print("printing scope:"+scope)
    if code:
        data = postrequest(url,data)
        print("logging in")
        print(data)
        session['access_token'] = data["access_token"]
        session['refresh_token'] = data["refresh_token"]

        if not validate_access_token():
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

@app.route('/graph', methods=['POST'])
def graph():
    '''
    post from submission, sets the page for /submit and gets graph
    Returns: /submit template page
    '''
    jobs = q.jobs  # Get a list of jobs in the queue
    message = None
    if request.method == 'POST':
        if validate_access_token():
            login = html.escape(request.form['login'])
            if str(login) == '':
                print("empty user")
                return jsonify({'data': "empty user"})
            login = str(login)
            userdata = getuser(login)
            if len(userdata) == 0:
                return jsonify({'data': "user doesn't exist."})
            print("inserting follows2 for graph")
            #remember followdata is already sorted by most recent follow date
            return_task = insertfollows2(userdata)
            return return_task
        else:
            return redirect(
                'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
            .format(CLIENT_ID, REDIRECT_URI, SCOPE))

    else:
        return'Bad Request', 400

@app.route('/history',methods = ['POST'])
def history():
    '''
    post from submission, sets the page for /submit and gets graph
    Returns: /submit template page
    '''
    if request.method == 'POST':
        if validate_access_token():
            login = html.escape(request.form['login'])
            if str(login) == '':
                print("empty user")
                return jsonify({'data': "empty user"})
            login = str(login)
            userdata = getuser(login)
            if len(userdata) == 0:
                return jsonify({'data': "user doesn't exist."})
            print("inserting follows2 for history")
            return_task = insertfollows2(userdata)
            return return_task
            
        else:
            return redirect(
                'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
            .format(CLIENT_ID, REDIRECT_URI, SCOPE))
    else:
        return'Bad Request', 400

@app.route("/results/<job_key>/<output>", methods=['GET'])
def get_results(job_key, output):

    job = Job.fetch(job_key, connection=conn)
    print("testing "+job.get_status())
    if job.is_finished:
        print("inserting allfollows")
        insertallfollows(job.result[0], job.result[3])
        userdata = job.result[1]
        print("getting followdata")
        followdata2 = getfollowdata(userdata[0]["id"], job.result[2])
        userlist = []
        for follower in followdata2["data"]:
            userlist.append(('id',follower["to_id"]))
            follower["followed_at"] = datetime.datetime.strptime(
                follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')

        print("entering getmultiuserinfo function")
        multiuserinfo = getMultiUserInfo(userlist)
        print("leaving getmultiuserinfo function")
        #sorts multiuserinfo by follow date
        object_map = {o['id']: o for o in multiuserinfo}
        multiuserinfo = []
        for id in followdata2["data"]:
            if id["to_id"] in object_map:
                multiuserinfo.append(object_map[id["to_id"]])
        print("leaving follow")

        firstfollow = followdata2["data"][len(followdata2["data"]) - 1]["followed_at"]
        print(firstfollow)
        now = datetime.datetime.utcnow()
        print(now)
        #setting up which html file to direct to
        htmlfile = "index.html"
        if output == "graph":
            htmlfile = "graph.html"
        elif output == "history":
            followdata2 = addvideoinfo(followdata2)
            htmlfile = "follow.html"
        print("finished making output")
        firstfollow = (now - firstfollow).total_seconds()
        return jsonify({'data': render_template(htmlfile,
            data = multiuserinfo,
            followdata = followdata2["data"],
            firstfollow = firstfollow,
            followlen = followdata2["total"],
            userdata=job.result[1]),
            'status':200
        })
    else:
        print("polling" + job.get_status())
        return jsonify({'data':job.description,
            'status':202,
            'job_status':job.get_status()

        })

@app.route('/adduser', methods=['POST'])
def adduser():
    '''
    from submission, checks and adds users to their save history
    Returns: 'success' if it works
    '''
    print("entering adduser")
    if request.method == 'POST' and "user_id" in session:
        login = html.escape(request.form['login'])
        user_id = html.escape(request.form['user_id'])
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
        login = html.escape(request.form['login'])
        user_id = html.escape(request.form['user_id'])
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

def insertfollows(user_id):
    '''
    parameter: user_id (Integer)
    inserts followdata for a user
    '''
    print("inserting new followers")
    print(user_id)
    followdata = getfollowers(user_id)
    timenow = datetime.datetime.utcnow()
    dbdata2 = SavedFollows(user_id, timenow)
    db.session.add(dbdata2)
    db.session.commit()
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

def getfollowdata(user_id, followdata):
    '''
    calls to get follows of a twitch user_id with common follows and triadic closures
    returns followdata json with additional info on each follow
    '''
    commonfollowsession = {}
    familiarfollowers = {}
    triad = {}
    followtotal = getfollowtotal(user_id)

    firstfollow = datetime.datetime.strptime(followdata["data"][len(followdata["data"]) - 1]["followed_at"], '%Y-%m-%dT%H:%M:%SZ')

    if "user_id" in session and session["user_id"] != user_id :
        userselect = session["user_id"]
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

def insertfollows2(userdata):
    '''
    inserts follows of deepness 2
    '''
    print("inserting followdata")
    user_id = userdata[0]["id"]
    #delete and add followers of this user_id
    db.session.execute(
        text('DELETE FROM Followcache WHERE from_id = :user_id '),
        {"user_id":int(user_id)})
    followdata2 = insertfollows(user_id)
    
    #get all id that I don't have followdata of yet
    rs = db.session.execute(
            text('''SELECT t1.to_id
            FROM Followcache t1
            LEFT JOIN SavedFollows t2 ON t2.to_id = t1.to_id
            WHERE t1.from_id = :user_id  AND t2.to_id IS NULL '''),
            {"user_id":int(user_id)})

    useridlist =[]
    #insert all new user_id
    for row in rs:
        useridlist.append(row.to_id)
    if len(useridlist) > 0:
        listlength = len(useridlist)
    else:
        listlength = "zero"
    task = q.enqueue(getallfollows, useridlist, userdata, followdata2, session["access_token"], description=listlength)  # Send a job to the task queue

    jobs = q.jobs  # Get a list of jobs in the queue

    q_len = len(q)  # Get the queue length

    #insert history
    timenow = datetime.datetime.utcnow()
    if "user_id" in session:
        from_id = session["user_id"]
        to_id = user_id
        dbdata = Callhistory(from_id, to_id, timenow)
        db.session.add(dbdata)
        db.session.commit()
    return jsonify({'data': render_template("add_task.html",
        userdata= userdata,
        jobs=jobs,
        task=task),
        'job_id':task.id
    })

def insertallfollows(followdata, useridlist):
    timenow = datetime.datetime.utcnow()
    for user_id in useridlist:
        dbdata = SavedFollows(user_id, timenow)
        db.session.add(dbdata)
    db.session.commit()
    
    for follower in followdata:
        from_id = follower["from_id"]
        from_login = str(follower["from_login"])
        to_id = follower["to_id"]
        to_login = follower["to_login"]
        followed_at = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
        dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
        db.session.add(dbdata)
    db.session.commit()

    return "success"


if __name__ == '__main__':
    app.run()
   # testmode(ENVIRONMENT)
