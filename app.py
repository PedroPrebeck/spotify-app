import os
import time
import uuid
import redis
import spotipy
import pandas as pd
from dotenv import load_dotenv
from datetime import timedelta
from flask import Flask, redirect, request, session, render_template, jsonify, url_for
from flask_session import Session
from spotipy.oauth2 import SpotifyOAuth
from sklearn.cluster import KMeans

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Redis server configuration
redis_url = os.getenv('REDIS_URL')
app.config.update(
    SESSION_TYPE='redis',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_REDIS=redis.StrictRedis.from_url(redis_url),
    SESSION_COOKIE_NAME='spotify_session'
)

Session(app)

# Spotify API credentials
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
SCOPE = 'user-top-read playlist-modify-public'

sp_oauth = SpotifyOAuth(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI, scope=SCOPE)

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    session.clear()  # Clear session at the beginning of login
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    session['id'] = str(uuid.uuid4())
    session['user_id'] = token_info['access_token']  # Store unique user ID for debugging

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_profile = sp.current_user()
    session.update(
        spotify_user_id=user_profile['id'],
        user_name=user_profile['display_name']
    )

    print(f"[DEBUG] New session started for user: {session['spotify_user_id']} ({session['user_name']}), session ID: {session['id']}")
    return redirect('/create_playlist')

def get_token():
    token_info = session.get('token_info', {})
    if not token_info:
        print("[DEBUG] No token found in session.")
        return None
    now = int(time.time())
    if token_info['expires_at'] - now < 60:
        print("[DEBUG] Token expired, refreshing...")
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  # Update session with new token info
    return token_info

@app.route('/create_playlist')
def create_playlist():
    token_info = get_token()
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_profile = sp.current_user()
    user_id = user_profile['id']

    if user_id != session.get('spotify_user_id'):
        print("[DEBUG] Token does not match the session user ID.")
        return redirect('/logout')

    print(f"[DEBUG] Creating playlist for user: {user_profile['display_name']} ({user_id}), session ID: {session['id']}")

    top_tracks = sp.current_user_top_tracks(limit=50)
    track_ids = [track['id'] for track in top_tracks['items']]
    track_names = [track['name'] for track in top_tracks['items']]
    features = sp.audio_features(track_ids)
    features_df = pd.DataFrame(features)

    kmeans = KMeans(n_clusters=3, random_state=0).fit(features_df[['danceability', 'energy', 'valence']])
    features_df['cluster'] = kmeans.labels_
    frequent_cluster = features_df['cluster'].value_counts().idxmax()
    cluster_tracks = features_df[features_df['cluster'] == frequent_cluster]

    genres = []
    for track_id in cluster_tracks['id']:
        track = sp.track(track_id)
        artist_id = track['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres.extend(artist['genres'])
    
    top_genre = pd.Series(genres).value_counts().idxmax()

    session.update(
        cluster_tracks=cluster_tracks['id'].tolist(),
        playlist_name='Clustered Playlist'
    )

    return render_template('playlist.html', top_genre=top_genre, track_names=track_names, user_name=user_profile['display_name'])

@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    token_info = get_token()
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_profile = sp.current_user()
    user_id = user_profile['id']

    if user_id != session.get('spotify_user_id'):
        print("[DEBUG] Token does not match the session user ID.")
        return redirect('/logout')

    playlist_name = session.get('playlist_name', 'Clustered Playlist')
    track_ids = session.get('cluster_tracks', [])

    if not track_ids:
        return redirect('/create_playlist')

    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return jsonify({'playlist_url': playlist['external_urls']['spotify']})

@app.route('/logout')
def logout():
    print(f"[DEBUG] Logging out user: {session.get('spotify_user_id')} ({session.get('user_name')}), session ID: {session.get('id')}")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)