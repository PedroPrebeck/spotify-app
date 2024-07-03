from flask import Flask, request, redirect, session, render_template, jsonify, url_for
import os
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from sklearn.cluster import KMeans
from dotenv import load_dotenv
from flask_session import Session
import redis

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Redis server configuration
redis_url = os.getenv('REDIS_URL')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.StrictRedis.from_url(redis_url)

Session(app)

# Set your Spotify API credentials from environment variables
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
SCOPE = 'user-top-read playlist-modify-public'

sp_oauth = SpotifyOAuth(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI, scope=SCOPE)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    session["user_id"] = token_info['access_token']  # Store unique user ID for debugging
    print(f"[DEBUG] New session started for user: {session['user_id']}")
    return redirect('/create_playlist')

def get_token():
    token_info = session.get("token_info", {})
    if not token_info:
        print("[DEBUG] No token found in session.")
        return redirect('/')
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        print("[DEBUG] Token expired, refreshing...")
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session["token_info"] = token_info  # Update session with new token info
    return token_info

@app.route('/create_playlist')
def create_playlist():
    token_info = get_token()
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])

    user_profile = sp.current_user()
    user_name = user_profile['display_name']
    print(f"[DEBUG] Creating playlist for user: {user_name}, session ID: {session['user_id']}")

    # Get user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=50)
    track_ids = [track['id'] for track in top_tracks['items']]
    track_names = [track['name'] for track in top_tracks['items']]
    
    # Get audio features for the tracks
    features = sp.audio_features(track_ids)
    features_df = pd.DataFrame(features)

    # Perform K-Means clustering
    kmeans = KMeans(n_clusters=3, random_state=0).fit(features_df[['danceability', 'energy', 'valence']])
    features_df['cluster'] = kmeans.labels_

    # Get tracks from the most frequent cluster
    frequent_cluster = features_df['cluster'].value_counts().idxmax()
    cluster_tracks = features_df[features_df['cluster'] == frequent_cluster]
    
    # Get genres
    genres = []
    for track_id in cluster_tracks['id']:
        track = sp.track(track_id)
        artist_id = track['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres.extend(artist['genres'])
    
    top_genre = pd.Series(genres).value_counts().idxmax()

    session['cluster_tracks'] = cluster_tracks['id'].tolist()
    session['playlist_name'] = 'Clustered Playlist'

    return render_template('playlist.html', top_genre=top_genre, track_names=track_names, user_name=user_name)

@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    token_info = get_token()
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])

    user_id = sp.me()['id']
    playlist_name = session.get('playlist_name', 'Clustered Playlist')
    track_ids = session.get('cluster_tracks', [])

    if not track_ids:
        return redirect('/create_playlist')

    # Create a new playlist
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)

    # Add tracks to the playlist
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return jsonify({'playlist_url': playlist['external_urls']['spotify']})

@app.route('/logout')
def logout():
    print(f"[DEBUG] Logging out user: {session.get('user_id')}")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
