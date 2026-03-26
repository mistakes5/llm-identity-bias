# 'user.*' → matches 'user.created', 'user.admin.updated'
# '*.event' → matches 'user.event', 'admin.event'
# '*' → matches everything
pattern = re.compile('^' + re.escape(pattern).replace(r'\*', '.*') + '$')

# 'user.*' → matches 'user.created', 'user.updated' only
# 'user.*.*' → matches 'user.admin.created' (requires 2 parts after 'user')
# '*' → matches 'user' only, NOT 'user.created'
segments = pattern.split('.')
regex_parts = []
for seg in segments:
    if seg == '*': regex_parts.append('[^.]+')  # one segment without dots
    else: regex_parts.append(re.escape(seg))
pattern = re.compile('^' + '\\.'.join(regex_parts) + '$')

# Pattern is already a regex string, just compile and use
pattern = re.compile(pattern)

def _compile_wildcard_pattern(self, pattern):
    """
    Compile a wildcard pattern to a regex pattern.
    
    Your 5-10 lines of code go here. Choose one of the three approaches above,
    or design your own. The only requirement is that it returns a compiled 
    re.Pattern object that can match event names.
    
    Args:
        pattern: The wildcard pattern from subscribe() (e.g., 'user.*')
    
    Returns:
        A compiled re.Pattern object
        
    Raises:
        ValueError: If the pattern is invalid
    """
    # TODO: Implement here
    raise NotImplementedError()