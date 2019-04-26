import sys
import os
import re

from pathlib import Path
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

import waitress
import flask

from werkzeug.wsgi import responder, FileWrapper
from werkzeug.wrappers import Request
from paste.cgiapp import CGIApplication

from globus_sdk import (NativeAppAuthClient, TransferClient,
                        RefreshTokenAuthorizer, TransferData)
from globus_sdk.exc import GlobusAPIError, TransferAPIError
from fair_research_login import NativeClient

def mkdir(p):
    """
    Creates a new directory p, unless the directory already exists.
    
    Arguments:
        p [Path] -- the path for the directory to be made
    """
    try:
        p.mkdir()
    except FileExistsError:
        pass

class LFS:

    def __init__(self, root):
        self.root = root

    @contextmanager
    def save(self, oid):
        """
        Creates any necessary (parent) directories.
        
        Decorator: contextmanager
        
        Argument:
            oid [str] -- the Object ID (OID)

        Returns: TBD
        """
        mkdir(self.root)

        tmpdir = self.root / 'tmp'
        mkdir(tmpdir)

        objects = self.root / 'objects'
        mkdir(objects)

        obj = self.path(oid)
        mkdir(obj.parent.parent)
        mkdir(obj.parent)

        with NamedTemporaryFile(dir=str(tmpdir), delete=False) as tmp:
            yield tmp

        Path(tmp.name).rename(obj)

    def path(self, oid):
        """
        Checks that the provided OID does not have any '/'s and returns the full path for the OID.
        
        Arguments:
            oid [str] -- the Object ID (OID)
        
        Returns: path to the OID (e.g., <root>/0d/a3/b17d9...3f65)
        """

        assert '/' not in oid
        return self.root / 'objects' / oid[:2] / oid[2:4] / oid

def create_git_app(repo):
    """
    Sets up the Git App (setting git project root and remote user). 
    
    Arguments:
        repo [str] -- the Git repo that the project is located in.

    Returns: the 'git app'
    """
    git_http_backend = Path(__file__).parent.absolute() / 'git-http-backend'
    cgi = CGIApplication({}, str(git_http_backend))

    @responder
    def git_app(environ, start_response):
        environ['GIT_PROJECT_ROOT'] = repo
        environ['REMOTE_USER'] = environ.get('HTTP_X_FORWARDED_USER')
        return cgi

    return git_app

def create_app(config_pyfile=None, config=None):
    """
    Creates the Flask app, including routes.

    Arguments:
        config_pyfile [File] -- (optional) python config file; defaults to None
        config [File] -- (optional) config file; defaults to None

    Functions:
        open_lfs -- returns an instance of the LFS class
        dispatch -- TBD
        data_url -- returns the full server URL based on the repo and OID

    "Route" Functions:
        lfs_objects -- creates/uploads lfs objects (WIP)
        lfs_get_oid -- retrieves information about a specific object?
        batch -- handles batch request(s)
        upload -- handles the 'upload' request operation
        download -- handles the 'download' request operation

    Returns: app (Flask object)
    """
    app = flask.Flask(__name__)
    if config_pyfile:
        app.config.from_pyfile(config_pyfile)
    if config:
        app.config.update(config)
    git_app = create_git_app(app.config['GIT_PROJECT_ROOT'])

    def open_lfs(repo):
        """
        Returns an instance of the LFS class.
        """

        return LFS(Path(app.config['GIT_PROJECT_ROOT']) / repo / 'lfs')

    @responder
    def dispatch(environ, start_response):
        """
        Compares the path from the Request (initialized by environ) to the git backend urls.
        If a match (using regular expression comparison) is found, error(s) get stored and the app is returned.
        Otherwise returns flask_wsgi_app.
        
        Decorator: responder

        Arguments:
            environ [type] -- used to initialize the Request (WIP)
            start_response [type] -- TBD
        
        Returns: flask_wsgi app -- returns an value as a wsgi app
        """

        request = Request(environ, shallow=True)

        git_backend_urls = [
            r'^/[^/]+/info/refs$',
            r'^/[^/]+/git-receive-pack$',
            r'^/[^/]+/git-upload-pack$',
        ]
        if any(re.match(p, request.path) for p in git_backend_urls):
            environ['wsgi.errors'] = environ['wsgi.errors'].buffer.raw
            return git_app

        return flask_wsgi_app

    flask_wsgi_app = app.wsgi_app
    app.wsgi_app = dispatch

    def data_url(repo, oid):
        """
        Returns the url for an object (given oid) in a specified repo. Uses the 'SERVER_URL' specified in app.config.
        
        Arguments:
            repo [str] -- the name of the repo (?)
            oid [str] -- the object id
        
        Returns: [str] -- the url for the specified object in the repo.
        """

        # example: http://localhost:5000/repo.git/lfs/<oid>
        return app.config['SERVER_URL'] + '/' + repo + '/lfs/' + oid

    @app.route('/<repo>/info/lfs/objects', methods=['POST'])
    def lfs_objects(repo):
        """
        Retrieves an OID from the flask request and adds the oid to the specified repo.
        
        Decorator: app.route('/<repo>/info/lfs/objects', methods=['POST'])

        Arguments:
            repo [str] -- the url (HTTP or SSH) of the repo that the object will be added to
        
        Returns: resp [json?] -- the response to the request in JSON format. 
        """

        oid = flask.request.json['oid']
        resp = flask.jsonify({
            '_links': {
                'upload': {
                    'href': data_url(repo, oid),
                },
            },
        })
        resp.status_code = 202
        return resp

    @app.route('/<repo>/info/lfs/objects/<oid>')
    def lfs_get_oid(repo, oid):
        """
        Given OID, attempts retrieves the object data from the specified repo.
        
        Decorator: app.route('/<repo>/info/lfs/objects/<oid>')

        Arguments:
            repo [str] -- the repo that the object to be retrieved is stored in
            oid [str?] -- the object id
        
        Returns: [WIP] -- the object, in JSON format (WIP).
        """

        oid_path = open_lfs(repo).path(oid)
        if not oid_path.is_file():
            flask.abort(404)
        return flask.jsonify({
            'oid': oid,
            'size': oid_path.stat().st_size,
            '_links': {
                'download': {
                    'href': data_url(repo, oid),
                },
            },
        })

    @app.route('/<repo>/info/lfs/objects/batch', methods=['POST'])
    def batch(repo):
        """
        See GitLFS Batch API for more info (https://github.com/git-lfs/git-lfs/blob/master/docs/api/batch.md).

        Decorator: app.route('<repo>/info/lfs/objects/batch', methods=['POST'])
        
        Arguments:
            repo [str] -- the Git repository where the LFS objects will be stored? 

        Functions:
            respond -- returns the response to the request, in JSON format. 
        
        Returns: [JSON] -- the response to the (batch) request.
        """

        req = flask.request.json
        print("REQUEST")
        print(req)
        lfs_repo = open_lfs(repo)

        if req['operation'] == 'download':
            assert 'basic' in req.get('transfers', ['basic'])

            def respond(obj):
                """
                Handles the response to a 'download' request.
                
                Arguments:
                    obj [object] -- an LFS(?) object
                
                Returns: [JSON] -- either the response data for a file OR an error (response); in JSON format
                """

                oid = obj['oid']
                oid_path = lfs_repo.path(oid)
                url = data_url(repo, oid)
                if oid_path.is_file():
                    return {
                        'oid': oid,
                        'size': oid_path.stat().st_size,
                        'actions': {
                            'download': {'href': url},
                        },
                    }

                else:  # TODO test
                    return {
                        'oid': oid,
                        'error': {
                            'code': 404,
                            'message': "Object does not exist",
                        },
                    }

            headers = {'Content-Type': 'application/vnd.git-lfs+json'}
            resp = {
                'transfer': 'basic',
                'objects': [respond(obj) for obj in req['objects']],
            }

            return flask.jsonify(resp), 200, headers

        elif req['operation'] == 'upload':
            assert 'basic' in req.get('transfers', ['basic'])

            def respond(obj):
                """
                Handles the response to an 'upload' request.
                
                Arguments:
                    obj [object] -- an LFS(?) object
                
                Returns: [JSON] -- the response, in JSON format
                """

                oid = obj['oid']
                url = data_url(repo, oid)
                rv = {
                    'oid': oid,
                    'size': obj['size'],
                }
                oid = obj['oid']
                oid_path = lfs_repo.path(oid)
                url = data_url(repo, oid)
                if not oid_path.is_file():
                    rv['actions'] = {'upload': {'href': url}}
                return rv

            headers = {'Content-Type': 'application/vnd.git-lfs+json'}
            resp = {
                'transfer': 'basic',
                'objects': [respond(obj) for obj in req['objects']],
            }
            return flask.jsonify(resp), 200, headers

        else:
            flask.abort(400)

    @app.route('/<repo>/lfs/<oid>', methods=['PUT'])
    def upload(repo, oid):
        """
        Goes through flask.request.stream and saves it as an LFS object.

        Decorator: app.route('/<repo>/lfs/<oid>', methods=['PUT']) 
        
        Arguments:
            repo [str] -- the Git(LFS) repo (WIP)
            oid [str] -- the object id
        
        Returns: TBD
        """

        with open_lfs(repo).save(oid) as f:
            for chunk in FileWrapper(flask.request.stream):
                f.write(chunk)

        return flask.jsonify(ok=True)

    @app.route('/<repo>/lfs/<oid>')
    def download(repo, oid):
        """
        Attempts to download an OID.
        
        Arguments:
            repo [str] -- the Git(LFS) repo (WIP)
            oid [str] -- the object id
        
        Returns: TBD
        """

        oid_path = open_lfs(repo).path(oid)
        if not oid_path.is_file():
            flask.abort(404)
        return flask.helpers.send_file(str(oid_path))   # send_file: sends contents of file to client

    return app

def runserver(host, port, **kwargs):
    """
    Runs the GitLFS Server (WIP)
    
    Arguments:
        host [str] -- the host for the server
        port [int] -- the port for the server
    """

    app = create_app(**kwargs)
    def serve():
        from paste.translogger import TransLogger
        wsgi = TransLogger(app.wsgi_app)
        waitress.serve(wsgi, host=host, port=port)

    if app.config.get('RELOADER'):
        from werkzeug._reloader import run_with_reloader
        run_with_reloader(serve)
    else:
        serve()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_pyfile = sys.argv[1]
    else:
        config_pyfile = 'settings.py'

    port = int(os.environ.get('PORT') or 5000)
    runserver('localhost', port, config_pyfile=config_pyfile)
