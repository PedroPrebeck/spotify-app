import os
import time
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
import pandas as pd
from sklearn.preprocessing import StandardScaler, MultiLabelBinarizer
from sklearn.decomposition import PCA
from flask import session
from app.algorithms.kmeans_algorithm import KMeansAlgorithm
from app.algorithms.another_algorithm import AnotherAlgorithm

def create_spotify_oauth():
    cache_handler = FlaskSessionCacheHandler(session)
    return SpotifyOAuth(
        client_id=os.getenv('SPOTIPY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
        scope='user-top-read playlist-modify-public',
        cache_handler=cache_handler
    )

def get_token():
    token_info = session.get('token_info')
    if not token_info:
        return None

    now = int(time.time())
    is_token_expired = token_info['expires_at'] - now < 60

    if is_token_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info

    return token_info

def get_spotify_client():
    token_info = get_token()
    if not token_info:
        return None
    return Spotify(auth=token_info['access_token'])

def get_top_tracks(sp):
    top_tracks = sp.current_user_top_tracks(limit=50)
    tracks = [{
        'id': track['id'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'artist_id': track['artists'][0]['id'],  # additional feature
        'album_cover': track['album']['images'][0]['url'] if track['album']['images'] else '',
        'popularity': track['popularity'],  # additional feature
        'duration_ms': track['duration_ms'],  # additional feature
    } for track in top_tracks['items']]
    return tracks

def get_audio_features(sp, track_ids):
    audio_features = sp.audio_features(track_ids)
    features = pd.DataFrame(audio_features)
    features.set_index('id', inplace=True)
    return features

def get_artist_genres(sp, artist_ids):
    genres = []
    for artist_id in artist_ids:
        artist = sp.artist(artist_id)
        genres.append(artist['genres'])
    return genres

def encode_features(features, genres):
    mlb = MultiLabelBinarizer()
    genre_encoded = mlb.fit_transform(genres)
    genre_df = pd.DataFrame(genre_encoded, index=features.index, columns=mlb.classes_)
    combined_features = features.join(genre_df)
    return combined_features

def get_clustering_algorithm():
    # Logic to select which algorithm to use
    algorithm = os.getenv('CLUSTERING_ALGORITHM', 'kmeans')
    if algorithm == 'kmeans':
        return KMeansAlgorithm
    elif algorithm == 'another':
        return AnotherAlgorithm
    else:
        raise ValueError("Unknown clustering algorithm: {}".format(algorithm))

def perform_clustering(tracks, features):
    # Normalize the features
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    # Adjust n_components for PCA
    n_components = min(10, scaled_features.shape[1])
    
    # Reduce dimensionality
    pca = PCA(n_components=n_components)
    reduced_features = pca.fit_transform(scaled_features)
    
    # Perform clustering
    clustering_algorithm = get_clustering_algorithm()
    cluster_track_ids = clustering_algorithm.perform_clustering(tracks, pd.DataFrame(reduced_features, index=features.index))
    
    return cluster_track_ids

def get_top_genre(sp, cluster_track_ids):
    genres = []
    for track_id in cluster_track_ids:
        track = sp.track(track_id)
        artist_id = track['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres.extend(artist['genres'])

    top_genre = pd.Series(genres).value_counts().idxmax()
    return top_genre
