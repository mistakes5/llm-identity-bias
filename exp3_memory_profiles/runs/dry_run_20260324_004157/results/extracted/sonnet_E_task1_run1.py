def is_allowed(self):
    now = time.time()                    # Step 1: what time is it?
    
    # Step 2: keep only timestamps within the window
    self.timestamps = [
        t for t in self.timestamps
        if _____________________         # fill in the "recent enough" condition
    ]
    
    # Step 3: are we under the limit?
    if len(self.timestamps) < self.max_requests:
        self.timestamps._____(now)       # record this request (hint: list method)
        return True
    
    return False                         # over the limit — block it