from flask import Blueprint, session, redirect, request, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
import time
from app.utils import create_spotify_oauth, get_token, get_spotify_client

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@auth.route('/callback')
def callback():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('main.index'))

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
