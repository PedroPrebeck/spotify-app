from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify
from app.utils import get_spotify_client, get_top_tracks, get_audio_features, get_artist_genres, encode_features, perform_clustering, get_top_genre
import pandas as pd
import random

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

    df = pd.DataFrame(tracks).set_index('id')
    audio_features = audio_features.drop(columns=['duration_ms'])
    features = df.join(audio_features, rsuffix='_audio')

    features = encode_features(features, genres)

    feature_columns = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 
                       'instrumentalness', 'liveness', 'valence']
    feature_columns.extend(features.columns[features.columns.str.startswith('genre_')])
    features = features[feature_columns].copy()

    cluster_track_ids = perform_clustering(tracks, features)
    top_genre = get_top_genre(sp, cluster_track_ids)

    user_name = sp.current_user()['display_name']
    session['frequent_tracks'] = cluster_track_ids

    cluster_tracks = [track for track in tracks if track['id'] in cluster_track_ids]
    return render_template('playlist.html', user_name=user_name, top_genre=top_genre, tracks=cluster_tracks)

@main.route('/remove_song', methods=['POST'])
def remove_song():
    track_id = request.form.get('track_id')
    print(f"Attempting to remove track_id: {track_id}")  # Debugging information
    if 'frequent_tracks' in session:
        print(f"frequent_tracks before removal: {session['frequent_tracks']}")  # Debugging information
        try:
            session['frequent_tracks'].remove(track_id)
            session.modified = True  # Mark the session as modified to ensure changes are saved
            print(f"frequent_tracks after removal: {session['frequent_tracks']}")  # Debugging information
            return jsonify({'status': 'success'})
        except ValueError:
            print("Track not found in session")  # Debugging information
            return jsonify({'status': 'error', 'message': 'Track not found in session'})
    print("No tracks in session")  # Debugging information
    return jsonify({'status': 'error', 'message': 'No tracks in session'})

@main.route('/add_recommendations', methods=['POST'])
def add_recommendations():
    sp = get_spotify_client()
    if not sp:
        return jsonify({'status': 'error', 'message': 'User not logged in'})

    num_recommendations = int(request.form.get('num_recommendations', 5))
    frequent_tracks = session.get('frequent_tracks', [])
    seed_tracks = random.sample(frequent_tracks, min(len(frequent_tracks), 5))

    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=num_recommendations)
    new_tracks = recommendations['tracks']

    for track in new_tracks:
        if track['id'] not in frequent_tracks:
            frequent_tracks.append(track['id'])

    session['frequent_tracks'] = frequent_tracks  # Save updated list back to session
    return jsonify({'status': 'success', 'new_tracks': new_tracks})

@main.route('/save_playlist', methods=['POST'])
def save_playlist():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('auth.login'))

    user_id = sp.current_user()['id']
    track_ids = request.form.get('track_ids').split(',')

    playlist = sp.user_playlist_create(user_id, 'Top Tracks Cluster Playlist', public=True)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return redirect(playlist['external_urls']['spotify'])