recent = get_recent_timestamps(key, time_window)  # get the list
count  = len(recent)                              # count how many
return count < max_requests                       # True = allowed, False = blocked

return len(get_recent_timestamps(key, time_window)) < max_requests