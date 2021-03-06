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
import random
from functions import (postrequest, getrequest, getvideoID, insertfollows,
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
    login = db.Column(db.Unicode(100))
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
    from_login = db.Column(db.Unicode(100))
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.Unicode(100))
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
    from_id = db.Column(db.Integer)
    to_id = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime)
    def __init__(self, to_id, updated_at):
        self.to_id = to_id
        self.updated_at = updated_at

class SavedVideos(db.Model):
    '''
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'savedvideos'
    id = db.Column(db.Integer, primary_key=True)
    follow_id = db.Column(db.Integer, db.ForeignKey('followcache.id'), nullable = False)
    video_id = db.Column(db.Integer)
    watchtime = db.Column(db.Unicode(100))
    returninfo = db.Column(db.Unicode(100))
    updated_at = db.Column(db.DateTime)
    def __init__(self, follow_id, video_id, watchtime, returninfo, updated_at):
        self.follow_id = follow_id
        self.video_id = video_id
        self.watchtime = watchtime
        self.returninfo = returninfo
        self.updated_at = updated_at

class Comments(db.Model):
    '''
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    user_login = db.Column(db.Unicode(255))
    comment = db.Column(db.Unicode(100))
    updated_at = db.Column(db.DateTime)
    def __init__(self, user_id, user_login, comment, updated_at):
        self.user_id = user_id
        self.user_login = user_login
        self.comment = comment
        self.updated_at = updated_at



@app.route('/')
def index():
    '''
    / is the default page, sends people to redirect, people can deny
    '''
    print("scope print")
    print(SCOPE)
    session["env"] = ENV
    if not validate_access_token():
        return redirect(
            'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}'
        .format(CLIENT_ID, REDIRECT_URI, SCOPE))
    else:
        isindex = True
        
        rows = db.session.execute(
                text('''SELECT user_login, comment, updated_at
                FROM Comments
                ORDER BY updated_at DESC; ''' )
        )
        saved_comments = []
        for row in rows:
            saved_comments.append((row.user_login, row.comment, row.updated_at))
        return render_template('index.html', isIndex = isindex, saved_comments= saved_comments)

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

    # checks if user entered in session
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
        #check if user is logged in as a twitch user and not timedout
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
        #timed out twitch user
        elif "refresh_token" in session:
            print("redirecting to login")
            noredirect = False
        else:
            print("was originally anon, refresh token not in session and login, user_id not in post data")
            getanon()
    else:
        print("access_token not in session")
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
        print("access token status: " + str(validate_access_token()))
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
        return'Bad Request', 400

@app.route('/history',methods = ['POST'])
def history():
    '''
    post from submission, sets the page for /submit and gets graph
    Returns: /submit template page
    '''
    if request.method == 'POST':
        print("access token status: " + str(validate_access_token()))
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
        return'Bad Request', 400

@app.route("/results/<job_key>/<output>", methods=['GET'])
def get_results(job_key, output):

    job = Job.fetch(job_key, connection=conn)
    if not job.meta:
        job.meta['requestload'] = 0
        job.meta['requestdone'] = 0
        job.meta['requesttotal'] = 0
        job.save_meta()
    print("testing "+job.get_status())
    if job.is_finished:
        userdata = job.result
        print("getting followdata")
        followdata = getfollowdata(userdata[0]["id"])
        userlist = []
        for follower in followdata["data"]:
            userlist.append(('id',follower["to_id"]))
        print("entering getmultiuserinfo function")
        multiuserinfo = getMultiUserInfo(userlist)
        print("leaving getmultiuserinfo function")
        #sorts multiuserinfo by follow date
        object_map = {int(o['id']): o for o in multiuserinfo}
        multiuserinfonew = []
        for id in followdata["data"]:
            if id["to_id"] in object_map:
                multiuserinfonew.append(object_map[id["to_id"]])
        deleteduser = {
        'id': '0',
        'login': 'Deleted',
        'display_name': 'Deleted',
        'type': '',
        'broadcaster_type': '',
        'description': 'This user is deleted',
        'profile_image_url': '//:0',
        'offline_image_url': '//:0',
        'view_count': 0,
        'created_at': '2020-01-01T00:00:00.000001Z'}
        for index, follow in enumerate(followdata["data"]):
            if index < len(multiuserinfonew) and int(multiuserinfonew[index]["id"]) != int(follow["to_id"]):
                print("inserting deleted user")
                print(index)
                print(follow["to_id"])
                deleteduser["id"] = str(follow["to_id"])
                multiuserinfonew.insert(index, deleteduser)
            elif index >= len(multiuserinfonew):
                print("inserting deleted user")
                print(index)
                print(follow["to_id"])
                deleteduser["id"] = str(follow["to_id"])
                multiuserinfonew.insert(index, deleteduser)
        print("finished sorting and inserting multiuserinfo")
        firstfollow = 0
        if len(followdata["data"]) > 0:
            firstfollow = followdata["data"][len(followdata["data"]) - 1]["followed_at"]
            print(firstfollow)
            now = datetime.datetime.utcnow()
            print(now)
            firstfollow = (now - firstfollow).total_seconds()
        #setting up which html file to direct to
        htmlfile = "index.html"
        if output == "graph":
            htmlfile = "graph.html"
        elif output == "history":
            htmlfile = "follow.html"
        print("finished making output")
        print(followdata["data"][0]["video_id"])
        return jsonify({'data': render_template(htmlfile,
            data = multiuserinfonew,
            followdata = followdata["data"],
            firstfollow = firstfollow,
            followlen = followdata["total"],
            userdata=job.result),
            'status':200
        })
    else:
        print("polling" + job.get_status())
        print("job position " + str(job.get_position()))
        print(job.meta)
        return jsonify({'data':job.description,
            'status':202,
            'job_status':job.get_status(),
            'user_id':job.meta['requestload'],
            'index':job.meta['requestdone'],
            'listlength':job.meta['requesttotal'],
            'job_position': str(job.get_position())

        })

@app.route('/addcomment', methods=['POST'])
def addcomment():
    '''
    from submission, adds a comment
    '''
    print("entering comment")
    if request.method == 'POST' and "user_id" in session:
        comment = html.escape(request.form['comment'])
        #insert comment
        timenow = datetime.datetime.utcnow()
        from_id = session["user_id"]
        from_login = session["login"]
        dbdata = Comments(from_id, from_login, comment, timenow)
        db.session.add(dbdata)
        db.session.commit()
        print('saved')
        return 'Success'
    else:
        return 'Failure'

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
    
    rows = db.session.execute(
            text('''SELECT COUNT(*) AS total
            FROM Followcache
            WHERE from_id = :user_id; ''' ),
            {"user_id":int(user_id)})

    
    for row in rows:
        follow_id = user_id
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
    commonfollowsession = {}
    familiarfollowers = {}
    triad = {}
    followtotal = getfollowtotal(user_id)
    followdata = {"data":[],"total":0}
    triadcount = {}
    if user_id in followtotal and followtotal[user_id] > 0:
        print("followtotalsuccess")
        followdata["total"] = followtotal[user_id]
        rows = db.session.execute(
            text('''SELECT t1.from_id as from_id,
            t1.from_login as from_login, 
            t1.to_id as to_id,
            t1.to_login as to_login,
            t1.followed_at as followed_at,
            t1.updated_at as updated_at,
            t2.video_id as video_id,
            t2.watchtime as watchtime,
            t2.returninfo as returninfo
            FROM Followcache t1 LEFT JOIN savedvideos t2 ON t1.id = t2.follow_id
            WHERE t1.from_id = :user_id
            ORDER BY t1.followed_at DESC; '''),
            {"user_id":int(user_id)})
        for row in rows:
            followinfo = {}
            followinfo["from_id"] = row.from_id
            followinfo["from_login"] = row.from_login
            followinfo["to_id"] = row.to_id
            followinfo["to_login"] = row.to_login
            followinfo["followed_at"] = row.followed_at
            followinfo["updated_at"] = row.updated_at
            followinfo["video_id"] = str(row.video_id)
            followinfo["watchtime"] = str(row.watchtime)
            followinfo["video_info"] = str(row.returninfo)
            followdata["data"].append(followinfo)
            
        firstfollow = followdata["data"][len(followdata["data"]) - 1]["followed_at"]

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
            from_id = str(row.from_id)
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
            if from_id in triadcount:
                triadcount[from_id].append((row.to_login, row.to_id, followtime))
            else:
                triadcount[from_id]=[(row.to_login, row.to_id, followtime)]

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
            if follow_id in triadcount:
                followdata["data"][index]["triadcount"] = triadcount[follow_id]
            followdata["data"][index]["followtime"] = (
                followdata["data"][index]["followed_at"] - firstfollow).total_seconds()
    return followdata

def getfollowamount(user_id):
    '''
    Calls twitch api to get followers of a specific userid:
    Parameters: user_id
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
        ('to_id', user_id),
        ('first', 1),
    )
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    url = 'https://api.twitch.tv/helix/users/follows?'
    data = getrequest(url, headers, params, 1)
    if "total" in data:
        print(data["total"])
    else:
        print("0")
        data["total"] = 0
    return data

def insertfollows2(userdata):
    '''
    inserts follows of deepness 2
    '''
    print("inserting followdata")
    user_id = userdata[0]["id"]
    #delete and add followers of this user_id
    insertfollows(user_id)
    
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
    listlength = len(useridlist)
    print("useridlist")
    while listlength > 100:
        task = q.enqueue(getallfollows, userdata, session["access_token"], description='Inserting 100 for '+userdata[0]["login"])
        listlength -= 100
    listlengthstr = str(listlength)
    task = q.enqueue(getallfollows, userdata, session["access_token"], description=listlengthstr)  
    # Send a job to the task queue

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

def getfollows(user_id, stopped_at, second):
    '''
    analysis of twitch data must call twice in order to work
    stopped_at is if the call interrupted
    second == finished will do the analysis
    '''
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
        ('to_id',user_id),
        ('first', 100),
    )
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }

    url = 'https://api.twitch.tv/helix/users/follows?'
    totaldata = {"data":[]}
    totaldatalen = 0
    k_connect = {}
    triad = {}
    popularity = {}
    lookup = {}
    print(second)
    if second == "finished":
        print("entering finished and getting followers of userid")
        rows = db.session.execute(
            text('''SELECT t1.from_id as from_id,
            t1.from_login as from_login, 
            t1.to_id as to_id,
            t1.to_login as to_login,
            t1.followed_at as followed_at
            FROM Followcache t1
            WHERE t1.to_id = :user_id
            ORDER BY t1.followed_at DESC; '''),
            {"user_id":int(user_id)})
        for row in rows:
            followinfo = {}
            followinfo["from_id"] = row.from_id
            followinfo["from_login"] = row.from_login
            followinfo["to_id"] = row.to_id
            followinfo["to_login"] = row.to_login
            followinfo["followed_at"] = (row.followed_at).strftime("%m/%d/%Y, %H:%M:%S")
            totaldata["data"].append(followinfo)
            k_connect[str(row.from_id)] = []
            triad[str(row.from_id)] = []
            popularity[str(row.from_id)] = 0
            lookup[str(row.from_id)] = row.from_login
        print("getting k-connect")
        #t1 is all followers of streamer
        #t2 is the follows of follower
        #t3 is again all followers of streamer
        rows = db.session.execute(
            text('''SELECT 
            t1.from_id as from_id, t2.to_id as to_id
            FROM Followcache t1, Followcache t2, Followcache t3
            WHERE t1.to_id = :user_id 
            AND t2.from_id = t1.from_id
            AND t3.to_id = :user_id
            AND t3.from_id = t2.to_id; '''),
            {"user_id":int(user_id)})
        for row in rows:
            k_connect[str(row.from_id)].append(row.to_id)
        #D gets all followers of streamer
        #A gets all the follows of the follower
        #B gets all the follows of the follows
        #C gets all the follows of the follower to calculate closure
        print("getting triads")
        rows = db.session.execute(
            text('''SELECT A.from_id as origin_id,
            A.to_id AS from_id
            FROM Followcache A, Followcache B, Followcache C, Followcache D
            WHERE D.to_id = :user_id AND A.from_id = D.from_id AND C.from_id = D.from_id  
            AND A.to_id  = B.from_id AND B.to_id = C.to_id AND C.to_id = :user_id
            AND A.followed_at < C.followed_at AND B.followed_at < C.followed_at; ''' ),
            {"user_id":int(user_id)})
        print("finished getting triads")
        for row in rows:
            triad[str(row.origin_id)].append(str(row.from_id))
        totaldatalen = len(totaldata["data"])
        print(totaldatalen)
    else:
        totaldata = getrequest(url, headers, params, pagination=100000)
        
        totaldatalen = int(totaldata["total"])
        print(totaldatalen)
   
    if second == "first":
        csv_columns = ['from_id', 'from_login', 'from_name',
            'to_id', 'to_login','to_name','followed_at']
        csv_file = "Names.csv"
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writeheader()
                for data in totaldata["data"]:
                    writer.writerow(data)
        except IOError:
            print("I/O error")
    print("inserting follows of user")
    streamerfollowdata = insertfollows(user_id)
    csv_columns2 = ['from_id', 'from_login', 'from_name', 'to_id', 'to_login',
    'to_name','followed_at','closure','triad', 'k-connected', 'total_connected','in-degree']
    csv_file2 = "Names2.csv"
    if second == "finished":
        try:
            openfile = open(csv_file2, 'w', newline='', encoding='utf-8')
            writer = csv.DictWriter(openfile, fieldnames=csv_columns2)
            writer.writeheader()
            openfile.close()
        except IOError:
            print("I/O error")
    csv_columns3 = ['nodeamount', 'sn' ,'minimum', 'maximum', 'average', 'result']
    csv_file3 = "simulation.csv"

    try:
        with open(csv_file3, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns3)
            writer.writeheader()
            csvfile.close()
    except IOError:
        print("I/O error")
    
    csv_columns4 = ['follower_id', 'follower_login', 'amount']
    csv_file4 = "popularity.csv"

    try:
        with open(csv_file4, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns4)
            writer.writeheader()
            csvfile.close()
    except IOError:
        print("I/O error")
    print("now printing to names 2")
    n = {}
    timenow = datetime.datetime.utcnow()
    rows = db.session.execute(
        text('''SELECT t1.from_id as from_id, t1.from_login as from_login
        FROM Followcache t1
        WHERE t1.to_id = :user_id;'''),
        {"user_id":int(user_id)})
    donotinsert = {}
    for row in rows:
        donotinsert[str(row.from_id)] = row.from_login
    for i in range(stopped_at, totaldatalen):
        if second == "finished":
            eachfollowdata = totaldata["data"][i]
            follow_id = str(totaldata["data"][i]["from_id"])

            if len(triad[follow_id]) > 0:
                eachfollowdata["closure"] = 1
            else:
                eachfollowdata["closure"] = 0
            eachfollowdata["triad"] = triad[follow_id]
            for tri in triad[follow_id]:
                popularity[str(tri)] += 1
            eachfollowdata["k-connected"]= k_connect[follow_id]
            eachfollowdata["total_connected"] = len(eachfollowdata["k-connected"])
            k_connect_length = str(eachfollowdata["total_connected"])
            if k_connect_length in n:
                n[k_connect_length][0] += 1
                n[k_connect_length][1] += eachfollowdata["closure"]
            else:
                n[k_connect_length] = [1, eachfollowdata["closure"], 0]
            eachfollowdata["in-degree"] = totaldatalen - i
            try:
                with open(csv_file2, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=csv_columns2)
                    writer.writerow(eachfollowdata)
                    csvfile.close()
            except IOError:
                print("I/O error")
        else:
            print(i)
            if str(totaldata["data"][i]["from_id"]) not in donotinsert:
                follower = getfollowers(totaldata["data"][i]["from_id"])
                dbdata2 = SavedFollows(user_id, timenow)
                db.session.add(dbdata2)
                for follow in follower["data"]:
                    from_id = follow["from_id"]
                    from_login = str(follow["from_login"])
                    to_id = follow["to_id"]
                    to_login = str(follow["to_login"])
                    followed_at = datetime.datetime.strptime(follow["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
                    dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
                    db.session.add(dbdata)
                db.session.commit()
    #prints popular linkers
    for follower in popularity:
        if popularity[follower] > 0:
            follow = {}
            follow["follower_id"] = follower
            follow["follower_login"] = lookup[follower]
            follow["amount"] = popularity[follower]
            try:
                with open(csv_file4, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=csv_columns4)
                    writer.writerow(follow)
                    csvfile.close()
            except IOError:
                print("I/O error")

    for sn in n:
        n[sn][2] =  float(n[sn][1])/float(n[sn][0])
    if second == "finished":
        getsim(n)
        popularityanalysis()
    return

def getsim(n):
    print("getting sim")
    csv_columns3 = ['nodeamount', 'sn' ,'minimum', 'maximum', 'average', 'result']
    csv_file3 = "simulation.csv"
    for nodeamount in n:
        if n[nodeamount][0] > 5:
            print("doing" +nodeamount)
            #get 100 tests
            maximum = 0.0
            minimum = 1.0
            ratioarray = []
            for test in range(99):
                base = [0, 1]
                edges = []
                randomorder = []
                totaledges = 2*int(nodeamount) + 1
                for i in range(totaledges):
                    edges.append(0)
                    randomorder.append(i)
                ratios = []
                for i in range(n[nodeamount][0]):
                    random.shuffle(randomorder)
                    for k in range(len(edges)):
                        edges[k] = 0
                    triad = False
                    done = False
                    j = 0
                    while done == False:
                        edge = randomorder[j]
                        j += 1
                        #odd edges correlate to connection with base[0] and even to base[1]
                        if edge == totaledges - 1:
                            done = True
                        elif (edge % 2) == 0:
                            edges[edge] = 1
                            if edges[edge + 1] == 1:
                                triad = True
                                done = True
                        else:
                            edges[edge] = 1
                            if edges[edge - 1] == 1:
                                triad = True
                                done = True
                    if triad:
                        ratios.append(1.0)
                    else:
                        ratios.append(0.0)
                avgratio = sum(ratios)/len(ratios)
                if avgratio > maximum:
                    maximum = avgratio
                elif avgratio < minimum:
                    minimum = avgratio
                ratioarray.append(avgratio)
            print(ratioarray)
            avgratio = sum(ratioarray)/len(ratioarray)
            stats = {"nodeamount":int(nodeamount),"sn":n[nodeamount][0], "maximum":maximum,"minimum":minimum,"average":avgratio, "result":n[nodeamount][2]}
            try:
                with open(csv_file3, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=csv_columns3)
                    writer.writerow(stats)
                    csvfile.close()
            except IOError:
                print("I/O error")
    return

def popularityanalysis():
    reader = csv.reader(open('popularity.csv'))
    csv_columns = ['follower_id', 'follower_login', 'linkclosures',
        'followeramount']
    csv_file = "popularityanalysis.csv"
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
    except IOError:
        print("I/O error")
    result = {}
    for row in reader:
        key = row[0]
        if key in result:
            # implement your duplicate row handling here
            pass
        result[key] = row[1:]
    print(result)
    print("entering triad")
    for user_id in result:
        if user_id == 'follower_id':
            continue
        response = getfollowamount(int(user_id))
        follow = {}
        follow["follower_id"] = user_id
        follow["follower_login"] = result[user_id][0]
        follow["linkclosures"] = result[user_id][1]
        follow["followeramount"] = response["total"]
        try:
            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writerow(follow)
                csvfile.close()
        except IOError:
            print("I/O error")
    return


@app.route('/gettriads', methods=['POST'])
def gettriads():
    '''
    from submission, sets the page for /submit and calls to make recommendations
    Returns: /submit template page
    '''
    if request.method == 'POST' and (ENV == 'dev' or session["login"] == 'kawyua'):
        if 'login' not in request.form or 'stopped_at' not in request.form or 'second' not in request.form :
            return render_template('index.html', message='Input is wrong')
        login = request.form['login']
        stopped_at = int(request.form['stopped_at'])
        second = request.form['second']
        if login == '' or stopped_at == '' or second == '':
            print("empty triad form")
            print(login)
            print(stopped_at)
            print(second)
            #print("empty user")
            return render_template('index.html', message='Please enter required fields')
        userdata = getuser(login)
        print(login)
        print(stopped_at)
        print(second)
        print(userdata)
        if len(userdata) == 0:
            return render_template('index.html', message='User doesnt exist.')
        if second == "deleteusercomment":
            db.session.execute(
            text('''DELETE
            FROM Comments
            WHERE user_login = :user_login; ''' ),
            {"user_login":str(login)}
            )
            db.session.commit()
        else:
            getfollows(userdata[0]["id"], stopped_at, second)
        
        return render_template('index.html')
    else:
        return'Bad Request', 400

if __name__ == '__main__':
    app.run()
   # testmode(ENVIRONMENT)
