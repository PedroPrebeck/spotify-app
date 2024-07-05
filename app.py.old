import os
import time
from flask import Flask, session, redirect, request, url_for, render_template, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from sklearn.cluster import KMeans
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Set your Spotify API credentials from environment variables
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
SCOPE = 'user-top-read playlist-modify-public'

app.config['SPOTIPY_CLIENT_ID'] = SPOTIPY_CLIENT_ID
app.config['SPOTIPY_CLIENT_SECRET'] = SPOTIPY_CLIENT_SECRET
app.config['SPOTIPY_REDIRECT_URI'] = SPOTIPY_REDIRECT_URI
app.config['SESSION_TYPE'] = 'filesystem'

def create_spotify_oauth():
    cache_handler = FlaskSessionCacheHandler(session)
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_handler=cache_handler
    )

def get_token():
    token_info = session.get('token_info', None)
    if not token_info:
        return None

    now = int(time.time())
    is_token_expired = token_info['expires_at'] - now < 60

    if is_token_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info

    return token_info

@app.route('/')
def index():
    if 'token_info' in session:
        sp = Spotify(auth=session['token_info']['access_token'])
        user = sp.current_user()
        return render_template('index.html', user_name=user['display_name'])
    return render_template('index.html')

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('index'))

@app.route('/analyze_results')
def analyze_results():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    sp = Spotify(auth=token_info['access_token'])
    
    # Get user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=50)
    tracks = [{
        'id': track['id'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'album_cover': track['album']['images'][0]['url'] if track['album']['images'] else ''
    } for track in top_tracks['items']]
    
    track_ids = [track['id'] for track in tracks]
    
    # Create a DataFrame from audio features
    audio_features = sp.audio_features(track_ids)
    df = pd.DataFrame(audio_features)

    # Select features for clustering
    features = df[['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo']]

    # Perform KMeans clustering
    kmeans = KMeans(n_clusters=9, random_state=42).fit(features)
    df['cluster'] = kmeans.labels_
    
    # Get tracks from the most frequent cluster
    frequent_cluster = df['cluster'].value_counts().idxmax()
    cluster_tracks = df[df['cluster'] == frequent_cluster]
    
    # Get genres
    genres = []
    for track_id in cluster_tracks['id']:
        track = sp.track(track_id)
        artist_id = track['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres.extend(artist['genres'])
    
    top_genre = pd.Series(genres).value_counts().idxmax()
    
    user_name = sp.current_user()['display_name']
    session['frequent_tracks'] = cluster_tracks['id'].tolist()

    cluster_track_data = [track for track in tracks if track['id'] in session['frequent_tracks']]

    return render_template('playlist.html', user_name=user_name, top_genre=top_genre, tracks=cluster_track_data)

@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    sp = Spotify(auth=token_info['access_token'])

    # Get user ID and frequent tracks from session
    user_id = sp.current_user()['id']
    track_ids = session.get('frequent_tracks', [])

    # Create a new playlist
    playlist = sp.user_playlist_create(user_id, 'Top Tracks Cluster Playlist', public=True)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return redirect(playlist['external_urls']['spotify'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)