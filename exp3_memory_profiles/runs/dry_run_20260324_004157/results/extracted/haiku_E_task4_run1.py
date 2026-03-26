def _matches_pattern(self, event_name, pattern):
    """
    Check if an event name matches a wildcard pattern.
    
    Examples:
        "user.created" matches "user.*" → True
        "user.deleted" matches "user.*" → True
        "post.created" matches "user.*" → False
        "*" matches anything → True
    """
    # TODO: Replace this with your implementation!
    raise NotImplementedError("_matches_pattern not yet implemented")