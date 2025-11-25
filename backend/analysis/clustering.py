from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from typing import List, Dict
import pandas as pd

class FailureClusterer:
    def __init__(self, n_clusters=10):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=100)

    def cluster_failures(self, failures: List[str]) -> List[int]:
        """
        Clusters a list of failure stack traces/messages.
        Returns a list of cluster labels corresponding to the input list.
        """
        if not failures:
            return []
            
        # If we have fewer failures than clusters, reduce n_clusters
        n_samples = len(failures)
        if n_samples < self.n_clusters:
            self.kmeans.n_clusters = max(1, n_samples // 2) # Simple heuristic
            
        try:
            tfidf_matrix = self.vectorizer.fit_transform(failures)
            self.kmeans.fit(tfidf_matrix)
            return self.kmeans.labels_.tolist()
        except Exception as e:
            print(f"Clustering failed: {e}")
            # Fallback: assign everything to cluster 0
            return [0] * len(failures)

    def get_cluster_keywords(self, failures: List[str], labels: List[int]) -> Dict[int, List[str]]:
        """
        Extracts top keywords for each cluster to help identify the common theme.
        """
        # This is a bit more complex to implement efficiently with just sklearn
        # For now, we can just return representative failures
        return {}
