from flask import Blueprint, session, redirect, url_for, render_template
from app.utils import get_spotify_client, get_top_tracks, get_audio_features, get_artist_genres, encode_features, perform_clustering, get_top_genre
import pandas as pd  # Ensure this import is present

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if 'token_info' in session:
        sp = get_spotify_client()
        if sp:
            user = sp.current_user()
            return render_template('index.html', user_name=user['display_name'])
    return render_template('index.html')

@main.route('/analyze_results')
def analyze_results():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('auth.login'))

    tracks = get_top_tracks(sp)
    track_ids = [track['id'] for track in tracks]
    artist_ids = [track['artist_id'] for track in tracks]
    audio_features = get_audio_features(sp, track_ids)
    genres = get_artist_genres(sp, artist_ids)

    # Merge audio features with track metadata, avoiding overlapping columns
    df = pd.DataFrame(tracks).set_index('id')
    audio_features = audio_features.drop(columns=['duration_ms'])  # Remove overlapping column
    features = df.join(audio_features, rsuffix='_audio')

    # Encode genres and combine features
    features = encode_features(features, genres)

    feature_columns = ['energy', 'loudness', 'speechiness', 'acousticness', 
                       'instrumentalness', 'liveness', 'valence']
    feature_columns.extend(features.columns[features.columns.str.startswith('genre_')])  # Add encoded genre columns
    features = features[feature_columns].copy()

    cluster_track_ids = perform_clustering(tracks, features)
    top_genre = get_top_genre(sp, cluster_track_ids)

    user_name = sp.current_user()['display_name']
    session['frequent_tracks'] = cluster_track_ids

    cluster_tracks = [track for track in tracks if track['id'] in cluster_track_ids]
    return render_template('playlist.html', user_name=user_name, top_genre=top_genre, tracks=cluster_tracks)

@main.route('/save_playlist', methods=['POST'])
def save_playlist():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('auth.login'))

    user_id = sp.current_user()['id']
    track_ids = session.get('frequent_tracks', [])

    playlist = sp.user_playlist_create(user_id, 'Top Tracks Cluster Playlist', public=True)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return redirect(playlist['external_urls']['spotify'])
