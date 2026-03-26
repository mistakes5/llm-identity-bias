def calculate_score(user_data):
    points_score = user_data["points"] * POINTS_MULTIPLIER        # currently 1.5×
    contributions_score = user_data["contributions"] * CONTRIBUTIONS_MULTIPLIER  # currently 3×
    return points_score + contributions_score