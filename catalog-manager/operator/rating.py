
class Rating():
    def __init__(self, rating_score, total_ratings):
        self.rating_score = float(rating_score) if rating_score is not None else None
        self.total_ratings = int(total_ratings)
    def __eq__(self, rating):
        if isinstance(rating, Rating):
            return self.rating_score == rating.rating_score and self.total_ratings == rating.total_ratings
        return False