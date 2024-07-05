from sklearn.cluster import KMeans
import pandas as pd

class KMeansAlgorithm:
    @staticmethod
    def perform_clustering(tracks, features):
        kmeans = KMeans(n_clusters=9, random_state=42).fit(features)
        features['cluster'] = kmeans.labels_

        frequent_cluster = features['cluster'].value_counts().idxmax()
        cluster_tracks = features[features['cluster'] == frequent_cluster]
        cluster_track_ids = cluster_tracks.index.tolist()

        return cluster_track_ids
