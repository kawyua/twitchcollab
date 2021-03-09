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

http = requests.Session()
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CILENT_SECRET = os.getenv("CILENT_SECRET")


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

def getallfollows(useridlist, userdata, followdata2, access_token):
    followdata = []
    for user_id in useridlist:
        follows = getfollowers(user_id, access_token)
        followdata += follows["data"]
    return (followdata, userdata, followdata2, useridlist)

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

def addvideoinfo(followdata):
    '''
    calls getvideo_id and adds video_id, video_timestamp, video_info to followdata
    '''
    
    #sets limit to the first 20 calls because of timeout
    maximum_calls = 20
    #sets limit to past 60 days
    expiredate = datetime.datetime.utcnow() - datetime.timedelta(60)
    for index,twitchuser in enumerate(followdata["data"]):
        if twitchuser["followed_at"] > expiredate and maximum_calls > 0:
            videoinfo = getvideoID(twitchuser["to_id"], twitchuser["followed_at"])
            if videoinfo is not None:
                followdata["data"][index]["video_id"] = videoinfo[0]
                followdata["data"][index]["video_timestamp"] = videoinfo[1]
                followdata["data"][index]["video_info"] = videoinfo[2]
            maximum_calls -= 1
    return followdata

