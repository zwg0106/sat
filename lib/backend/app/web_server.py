import os
from flask_session import RedisSessionInterface
from redis import Redis
from time import ctime
import datetime
from logger import LOGGER
from forms import UploadForm
from flask import Flask, \
    jsonify, \
    render_template, \
    Response, \
    json, \
    make_response, \
    request, \
    redirect, \
    session, \
    abort, \
    send_from_directory, \
    g, \
    url_for
from decorators import login_required
import upload_processor
import uuid
from const import CFG_PATH
import configparser

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(CFG_PATH)

class SatWebServer(object):
    """This class manages the FLASK Web server."""

    def __init__(self, core):

        self.core = core
        self.app = Flask(
            __name__,  template_folder=os.path.join(BASE_DIR, 'templates'))
        self.app.config.from_object('const')
        self.sar_dir = self.app.config.get('SA_DIR')
        self.user = self.app.config.get('USER')
        self.passwd = self.app.config.get('PASSWORD')
        self.header_text = self.app.config['TEMPLATE_CONFIGURATION']['header_text']
        self._init_cache_db()
        self._route()
        self.app.before_request(self.before_request)

    def _init_cache_db(self):
        self.app.cache = Redis(host='redis', port=6379)
        self.app.cache.set("saDir", self.sar_dir)
        self.app.cache.set("uid_track", 1)
        self.app.cache.set("session_data", {})

        self.app.config['UPLOAD_FOLDER'] = os.path.dirname(
            os.path.abspath(__file__)) + self.sar_dir
        self.app.config['STATIC_FOLDER'] = os.path.dirname(
            os.path.abspath(__file__)) + '/static'

        self.app.session_interface = RedisSessionInterface(
            self.app.cache, key_prefix='SESSION', use_signer=True, permanent=False)
        self.app.permanent_session_lifetime = datetime.timedelta(hours=1)
        
        try:
            os.mkdir(self.sar_dir)
        except Exception as E:
            LOGGER.error("[%s] mkdir() -- [%s] : %s" %
                        (ctime(), self.sar_dir, E))

    def _route(self):
        """Define route."""
        self.app.add_url_rule('/', view_func=self._index, methods=['GET', ])
        self.app.add_url_rule(
            '/login/', view_func=self._login, methods=['GET', 'POST', ])
        self.app.add_url_rule('/logout/', view_func=self._logout)
        self.app.add_url_rule(
            '/upload/', view_func=self._upload, methods=['POST', ])
        
    @login_required
    def _index(self):
        form = UploadForm(request.form)

        return render_template('index.html',
                               user=g.user,
                               data=False,
                               form=form,
                               progress=0,
                               **self.app.config.get('TEMPLATE_CONFIGURATION'))

    @login_required
    def _upload(self):
        LOGGER.debug("current user <%s> " % (g.user))
        if request.method == 'POST':
            form = UploadForm(request.form)
            form.datafile = request.files.getlist("datafile")
            if form.validate_on_submit() or form.data['cmd_mode']:
                target = os.path.join(self.app.cache.get(
                    'saDir').decode('utf-8'), str(g.user_id))
                future = self.core.run_coroutine_threadsafe(
                    upload_processor.start, self.core, self.app.cache, target, g.user_id, form)
                _valid_results_found, response = future.result()
            else:
                return jsonify({'form data': 'INVALID'})

            LOGGER.debug(_valid_results_found)
            LOGGER.debug(response)

            dashboard_url = config.get('Grafana', 'dashboard_url')
            if not dashboard_url:
                import socket
                IP = socket.gethostbyname('frontend')
                dashboard_url = "http://%s:3000/" % IP

            for i in range(len(response['slug'])):
                response['nodenames_info'][i].append(dashboard_url + \
                                            ("dashboard/db/%s" % response['slug'][i]))

            LOGGER.debug(response['nodenames_info'])
            if form.data['cmd_mode']:
                res = {
                    "valid_results": _valid_results_found,
                    "data": response["nodenames_info"],
                    "redirect_url": dashboard_url
                }
                return jsonify(res)
            else:
                return render_template('results.html',
                                       user=g.user,
                                       data=response["nodenames_info"],
                                       form=form,
                                       valid_results=_valid_results_found,
                                       progress=100,
                                       **self.app.config.get('TEMPLATE_CONFIGURATION'))

            abort(405)

    def _login(self):
        if request.method == 'GET':
            return render_template('login.html', header_text=self.header_text)
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            if username != self.user or password != self.passwd:
                return u'username or password error'
            else:
                session['user'] = username
                g.user = session['user']
                g.user_id = uuid.uuid3(uuid.NAMESPACE_OID, g.user)

                return redirect(url_for('_index'))

    def _logout(self):
        session.clear()
        return redirect(url_for('_login'))

    def before_request(self):
        g.user = session.get('user')
        if g.user is not None:
            g.user_id = uuid.uuid3(uuid.NAMESPACE_OID, g.user)
            LOGGER.debug("user id is %s" % g.user_id)

    def start(self):
        try:
            self.app.run(host=self.app.config.get('HOST'),
                         port=self.app.config.get('PORT'),
                         debug=self.app.config.get('DEBUG'))
        except:
            raise
