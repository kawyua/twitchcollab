import re
import os
import requests
import datetime
from urllib import request
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from flask import session
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from rq import get_current_job
from sqlalchemy.orm import relationship

Base = declarative_base()
http = requests.Session()
load_dotenv()
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
POSTGRESQL_DATABASE_URI = os.getenv("POSTGRESQL_DATABASE_URI")
CLIENT_ID = os.getenv("CLIENT_ID")
CILENT_SECRET = os.getenv("CILENT_SECRET")

ENV = os.getenv("ENV")
if ENV == 'dev':
    engine = create_engine(POSTGRESQL_DATABASE_URI)

else:
    engine = create_engine(SQLALCHEMY_DATABASE_URI)


dbsession = sessionmaker(engine, future=True)

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

class Users(Base):
    """
    Stores user login history
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    login = Column(String(32))
    updated_at = Column(DateTime)
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    login = Column(Unicode(100))
    updated_at = Column(DateTime)
    def __init__(self, user_id, login, updated_at):
        self.user_id = user_id
        self.login = login
        self.updated_at = updated_at

class Callhistory(Base):
    '''
    stores the calls a user calls, anon has user_id = 0 and login = ""
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    login = Column(String(32))
    to_id = Column(Integer)
    to_login = Column(String(32))
    updated_at = Column(DateTime)
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
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    to_id = Column(Integer)
    updated_at = Column(DateTime)
    def __init__(self, user_id, to_id, updated_at):
        self.user_id = user_id
        self.to_id = to_id
        self.updated_at = updated_at

class Callsaved(Base):
    '''
    Save calls from a user 
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    login = Column(String(32))
    to_login = Column(String(32))
    updated_at = Column(DateTime)
    '''
    __tablename__ = 'callsaved'
    id = Column(Integer, primary_key=True)
    from_id = Column(Integer)
    from_login = Column(Unicode(100))
    to_id = Column(Integer)
    to_login = Column(Unicode(100))
    updated_at = Column(DateTime)
    def __init__(self, from_id, from_login, to_id, to_login, updated_at):
        self.from_id = from_id
        self.from_login = from_login
        self.to_id = to_id
        self.to_login = to_login
        self.updated_at = updated_at

class Followcache(Base):
    '''
    id = Column(Integer, primary_key=True)
    from_id = Column(Integer)
    from_login = Column(String(200), unique=True)
    to_id = Column(Integer)
    to_login = Column(String(200), unique=True)
    followed_at = Column(DateTime)
    updated_at = Column(DateTime)
    '''
    __tablename__ = 'followcache'
    id = Column(Integer, primary_key=True)
    from_id = Column(Integer)
    from_login = Column(Unicode(100))
    to_id = Column(Integer)
    to_login = Column(Unicode(100))
    followed_at = Column(DateTime)
    updated_at = Column(DateTime)
    def __init__(self, from_id, from_login, to_id, to_login, followed_at, updated_at):
        self.from_id = from_id
        self.from_login = from_login
        self.to_id = to_id
        self.to_login = to_login
        self.followed_at = followed_at
        self.updated_at = updated_at

class SavedFollows(Base):
    '''
    id = Column(Integer, primary_key=True)
    to_id = Column(Integer)
    to_login = Column(String(200), unique=True)
    updated_at = Column(DateTime)
    '''
    __tablename__ = 'savedfollows'
    id = Column(Integer, primary_key=True)
    to_id = Column(Integer)
    updated_at = Column(DateTime)
    def __init__(self, to_id, updated_at):
        self.to_id = to_id
        self.updated_at = updated_at

class SavedVideos(Base):
    '''
    id = db.Column(db.Integer, primary_key=True)
    to_id = db.Column(db.Integer)
    to_login = db.Column(db.String(200), unique=True)
    updated_at = db.Column(db.DateTime)
    '''
    __tablename__ = 'savedvideos'
    id = Column(Integer, primary_key=True)
    follow_id = Column(Integer, ForeignKey('followcache.id'), nullable = False)
    video_id = Column(Integer)
    watchtime = Column(Unicode(100))
    returninfo = Column(Unicode(100))
    updated_at = Column(DateTime)
    def __init__(self, follow_id, video_id, watchtime, returninfo, updated_at):
        self.follow_id = follow_id
        self.video_id = video_id
        self.watchtime = watchtime
        self.returninfo = returninfo
        self.updated_at = updated_at

def postrequest(url, data):
    '''
    pagination default is 1000
    '''
    try:
        response = http.post(url, data=data)
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
    return data

def getrequest(url, headers, params, pagination = 2000, donotretry=False):
    '''
    pagination default is 1000
    '''
    parameter = params
    header = headers
    totaldata = {"data":[]}

    i = 0
    while i < pagination and donotretry == False:
        try:
            response = http.get(url, headers=header, params=parameter)
            # If the response was successful, no Exception will be raised
            response.raise_for_status()
        except HTTPError as http_err:
            print('HTTP error occurred:{0}'.format(http_err))  # Python 3.6
            #refresh()
            #getrequest(url, headers, params)
            anon_access_token_header = get_app_access_token_header()
            return getrequest(url, anon_access_token_header, params, pagination, True)
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

def get_app_access_token_header(refresh_token = "none"):
    '''
    For people that do not login through their twitch,
    '''
    url ='https://id.twitch.tv/oauth2/token'
    data={'client_id':CLIENT_ID,
        'client_secret':CILENT_SECRET,
        'grant_type':'client_credentials'
        }
    response = postrequest(url, data)
    access_token = response['access_token']
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(session['access_token']),
    }
    return headers

def insertfollows(user_id):
    '''
    parameter: user_id (Integer)
    inserts followdata for a user
    '''
    
    with engine.connect() as con:
        con.execute(
        text('DELETE FROM savedfollows WHERE from_id = :user_id '),
        {"user_id":int(user_id)})
    print("inserting new followers")
    print(user_id)
    followdata = getfollowers(user_id)
    timenow = datetime.datetime.utcnow()
    dbdata2 = SavedFollows(user_id, timenow)
    with dbsession.begin() as session:
        print("entering follower save")
        session.add(dbdata2)
    
    followdata2 = {"data":[]}
    with engine.connect() as con:
        #get all id that I don't have followdata of yet
        rows = con.execute(
            text('''SELECT t1.from_id as from_id,
            t1.from_login as from_login, 
            t1.to_id as to_id,
            t1.to_login as to_login,
            t1.followed_at as followed_at,
            t1.updated_at as updated_at
            FROM Followcache t1
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
            followdata2["data"].append(followinfo)
    with dbsession.begin() as session:
        print("entering followers")
        for index, follower in enumerate(followdata["data"]):
            if len(followdata2["data"]) > 0 and datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ') > followdata2["data"][0]["followed_at"]:
                from_id = follower["from_id"]
                from_login = str(follower["from_login"])
                to_id = follower["to_id"]
                to_login = follower["to_login"]
                followed_at = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
                dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
                session.add(dbdata)
            elif len(followdata2["data"]) == 0:
                from_id = follower["from_id"]
                from_login = str(follower["from_login"])
                to_id = follower["to_id"]
                to_login = follower["to_login"]
                followed_at = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
                dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
                session.add(dbdata)

    return followdata

def getvideoID(userID, timestamp, access_token=""):
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
    
    if access_token == "":
        access_token = session['access_token']
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
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
                returninfo = video["title"][:75] + (video["title"][75:] and '..')
            return [video["id"], returntime, returninfo]

def getfollowers(userID, access_token=""):
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
    if access_token == "":
        access_token = session['access_token']
    params = (
        ('from_id',userID),
        ('first', 100),
    )
    headers = {
        'client-id': CLIENT_ID,
        'Authorization': 'Bearer {0}'.format(access_token),
    }
    url = 'https://api.twitch.tv/helix/users/follows?'
    data = getrequest(url, headers, params)
    return data

def getallfollows(userdata, access_token):
    job = get_current_job()
    useridlist =[]
    with engine.connect() as con:
        #get all id that I don't have followdata of yet
        rs = con.execute(
                text('''SELECT t1.to_id
                FROM Followcache t1
                LEFT JOIN SavedFollows t2 ON t2.to_id = t1.to_id
                WHERE t1.from_id = :user_id  AND t2.to_id IS NULL '''),
                {"user_id":int(userdata[0]["id"])})
        #insert all new user_id
        for row in rs:
            useridlist.append(row.to_id)
    
    listlength = len(useridlist)
    followdata = []
    
    #get each user's follow list
    for index, user_id in enumerate(useridlist):
        follows = getfollowers(user_id, access_token)
        job.meta['requestload'] = user_id
        job.meta['requestdone'] = index
        job.meta['requesttotal'] = listlength - 1
        job.save_meta()
        followdata += follows["data"]
    timenow = datetime.datetime.utcnow()
    #log user_id call
    with dbsession.begin() as session:
        for user_id in useridlist:
            dbdata = SavedFollows(user_id, timenow)
            session.add(dbdata)
    #add follows to database
        for follower in followdata:
            from_id = follower["from_id"]
            from_login = str(follower["from_login"])
            to_id = follower["to_id"]
            to_login = follower["to_login"]
            followed_at = datetime.datetime.strptime(follower["followed_at"], '%Y-%m-%dT%H:%M:%SZ')
            dbdata = Followcache(from_id, from_login, to_id, to_login, followed_at, timenow)
            session.add(dbdata)
    print("entering videoinfo")
    addvideoinfo(userdata[0]["id"], access_token)
    return userdata

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
    print("entering getmultiuserinfo while loop")
    while len(userlist) > count:
        if count < len(userlist):
            params = tuple(userlist[count:count+100])

        else:
            params = tuple(userlist)
        count += 100
        userinfolist += getrequest(url, headers, params)["data"]
    return userinfolist

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

def addvideoinfo(user_id, access_token):
    '''
    calls getvideo_id and adds video_id, video_timestamp, video_info to followdata
    '''
    
    job = get_current_job()
    print("inserting videoinfo")
    followdata = {"data":[],"total":0}
    with engine.connect() as con:
        rows = con.execute(
            text('''SELECT t1.id as id, t1.to_id as to_id, t1.followed_at as followed_at
            FROM Followcache t1
            LEFT JOIN SavedVideos t2 ON t2.follow_id = t1.id
            WHERE t1.from_id = :user_id  AND t2.id IS NULL 
            ORDER BY t1.followed_at ASC'''),
            {"user_id":int(user_id)})
        for row in rows:
            followinfo = {}
            followinfo["id"] = row.id
            followinfo["to_id"] = row.to_id
            followinfo["followed_at"] = row.followed_at
            followdata["data"].append(followinfo)
    #sets limit to past 60 days
    now = datetime.datetime.utcnow()
    expiredate = now - datetime.timedelta(60)
    
    with dbsession.begin() as session:
        for index,twitchuser in enumerate(followdata["data"]):
            
            job.meta['requestload'] = " video of "+ str(twitchuser["to_id"])
            job.meta['requestdone'] = index
            job.meta['requesttotal'] = len(followdata["data"]) - 1
            job.save_meta()
            if twitchuser["followed_at"] > expiredate:
                videoinfo = getvideoID(twitchuser["to_id"], twitchuser["followed_at"], access_token)
                if videoinfo is not None:
                    follow_id = twitchuser["id"]
                    video_id = videoinfo[0]
                    video_timestamp = videoinfo[1]
                    video_info = videoinfo[2]
                    updated_at = now
                    dbdata = SavedVideos(follow_id, video_id, video_timestamp, video_info, updated_at)
                    session.add(dbdata)
                else:
                    follow_id = twitchuser["id"]
                    video_id = 0
                    video_timestamp = twitchuser["followed_at"]
                    video_info = "expired"
                    updated_at = now
                    dbdata = SavedVideos(follow_id, video_id, video_timestamp, video_info, updated_at)
                    session.add(dbdata)
            else:
                follow_id = twitchuser["id"]
                video_id = 0
                video_timestamp = twitchuser["followed_at"]
                video_info = "expired"
                updated_at = now
                dbdata = SavedVideos(follow_id, video_id, video_timestamp, video_info, updated_at)
                session.add(dbdata)
    return "success"

