from flask import *
from datetime import datetime, timedelta
import time
from unidecode import unidecode
import os
import threading
import pickle
from functools import wraps
from flask_basicauth import BasicAuth

def persistent(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        loadState()
        ret = f(*args, **kwargs)
        saveState()
        return ret
    return wrapped

app = Flask(__name__)
app.secret_key = b'_5%yangr4Q8z\n\xec]/'
app.config['BASIC_AUTH_USERNAME'] = 'jack'
app.config['BASIC_AUTH_PASSWORD'] = 'telecomando'

basic_auth = BasicAuth(app)

RECORD = 0
PLAY = 1
record_request_ongoing = False
codes = {}
schedule = []
immediate_requests = []
lock = threading.Lock()
def saveState():
    lock.acquire()
    #print "Saving State"
    f = open("codes.p", "wb" )
    pickle.dump(codes, f)
    f.close()
    f = open("schedule.p", "wb" )
    pickle.dump(schedule, f)
    f.close()
    lock.release()

def loadState():
    lock.acquire()
    #print "Loading state"
    global codes
    global schedule
    if os.path.exists("codes.p"):
        f = open("codes.p", "rb")
        codes = pickle.load(f)
        f.close()
    if os.path.exists("schedule.p"):
        f = open("schedule.p", "rb")
        schedule = pickle.load(f)
        f.close()
    lock.release()

@app.route('/')
@basic_auth.required
@persistent
def main():
    loadState()
    return render_template('index.html', codes=codes, schedule=schedule)

@app.route('/scheduleAction', methods = ['POST'])
@basic_auth.required
@persistent
def scheduleAction():
    time_str = request.form.get("time", "")
    action = request.form.get("action", "")
    #print time_str, action
    if not time_str or not action:
        flash('Something was missing in the form.')
    else:
        time = datetime.strptime(time_str, '%H:%M')
        lastExecFake = time.replace(year=datetime.utcnow().year, month=datetime.utcnow().month, day=datetime.utcnow().day)
        now = datetime.utcnow()
        if (lastExecFake > now):
            lastExecFake = lastExecFake - timedelta(days=1)
        schedule.append({ "action" : action, "time" : time, "lastExec": lastExecFake })
        flash('Action correctly scheduled.')
    return redirect(url_for('main'))

@app.route('/removeSchedule/<name>/<time>')
@basic_auth.required
@persistent
def removeFromSchedule(name, time):
    time = datetime.strptime(time, '%H:%M')
    for i in range(len(schedule)):
        if schedule[i]['action'] == name and schedule[i]['time'] == time:
            schedule.pop(i)
            flash('Action "'+name+'" correctly removed from schedule.')
            return redirect(url_for('main'))
    flash('Could not find action "'+name+'",  failed to remove it from schedule.')
    return redirect(url_for('main'))

def getNextAction():
    if len(immediate_requests)>0:
        return immediate_requests.pop(0)
    for a in schedule:
        now = datetime.utcnow()
        action_time = a["time"].replace(year=datetime.utcnow().year, month=datetime.utcnow().month, day=datetime.utcnow().day)
        if (now>action_time):
            if not a["lastExec"] or (now - timedelta(days=1) > a["lastExec"]):
                #print "correct range for lastExec "+ str(a)
                a["lastExec"] = action_time;
                return [PLAY, a['action']]
    return None

@app.route('/getAction')
@basic_auth.required
@persistent
def getAction():
    global schedule
    #.replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
    global record_request_ongoing
    to_do = getNextAction()
    if to_do is None:
        return ""
    action = to_do
    if action[0] == PLAY:
        return str(PLAY)+","+unidecode(action[1]).ljust(50,'\x00')+codes[action[1]]
    elif action[0] == RECORD:
        return ",".join(map(str, action))
    return ""

@app.route('/postCode/<name>', methods = ['POST'])
@basic_auth.required
@persistent
def postCode(name):
    global codes
    global record_request_ongoing
    request.get_data()
    #print request.data
    codes[name] = request.data
    record_request_ongoing = False
    return ""

@app.route('/recordCode', methods=['POST'])
@basic_auth.required
@persistent
def record():
    global immediate_requests
    global record_request_ongoing
    name = request.form.get('name','')
    if name == '':
        flash('Invalid/empty name,  failed to record new code.')
        return redirect(url_for('main'))
    record_request_ongoing = True
    immediate_requests.append([RECORD,name])
    while record_request_ongoing:
        time.sleep(1)
    flash('Request correctly registered.')
    return redirect(url_for('main'))

@app.route('/deleteCode/<name>')
@basic_auth.required
@persistent
def deleteCode(name):
    global codes
    for i in codes.keys():
        if i == name:
            del codes[i]
            flash('Delete code "'+name+'".')
            return redirect(url_for('main'))
    flash('Could not find code "'+name+'".')
    return redirect(url_for('main'))

@app.route('/playCode/<name>')
@basic_auth.required
@persistent
def play(name):
    immediate_requests.append([PLAY,name])
    flash('Action successfully scheduled.')
    return redirect(url_for('main'))


@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    return date.strftime("%H:%M")
