# ========================================================================
# PUBLISH-SUBSCRIBE EVENT SYSTEM
# ========================================================================
# A simple pub-sub system where:
# - Functions "subscribe" to events
# - When you "publish" an event, all subscribed functions get called
# - You can subscribe to wildcards like "user.*" to catch multiple events

# Dictionary to store all subscribers
# Format: { "event_name": [callback1, callback2, ...] }
subscribers = {}


def subscribe(event_name, callback_function):
    """
    Subscribe a function to listen for an event.
    
    When that event is published, callback_function will be called
    with the event data.
    
    Args:
        event_name: Name of the event (e.g., "user_login")
                   Can use wildcards: "user.*" to match any user event
        callback_function: The function to call when event happens
    """
    # If this is the first subscriber to this event, create a list for it
    if event_name not in subscribers:
        subscribers[event_name] = []
    
    # Only add if not already subscribed (avoid duplicates)
    if callback_function not in subscribers[event_name]:
        subscribers[event_name].append(callback_function)
        print(f"✓ Subscribed to '{event_name}'")
    else:
        print(f"Already subscribed to '{event_name}'")


def unsubscribe(event_name, callback_function):
    """
    Stop listening to an event.
    
    Args:
        event_name: The event to stop listening to
        callback_function: The function to remove
    """
    # Check if this event exists and has subscribers
    if event_name in subscribers:
        # Check if this specific function is subscribed
        if callback_function in subscribers[event_name]:
            # Remove it from the list
            subscribers[event_name].remove(callback_function)
            print(f"✓ Unsubscribed from '{event_name}'")
        else:
            print(f"Function was not subscribed to '{event_name}'")
    else:
        print(f"No subscribers for '{event_name}'")


def publish(event_name, data=None):
    """
    Send/publish an event to all subscribers.
    
    This calls:
    1. All functions subscribed to this exact event
    2. All functions subscribed to matching wildcard patterns
    
    Args:
        event_name: Name of the event being published
        data: Information to send with the event (usually a dict)
    """
    # Count how many functions we're calling
    notify_count = 0
    
    # STEP 1: Call exact subscribers
    # Check if anyone subscribed to this specific event
    if event_name in subscribers:
        # Loop through each subscribed function
        for callback in subscribers[event_name]:
            # Call the function and pass the data
            callback(data)
            notify_count += 1
    
    # STEP 2: Call wildcard subscribers
    # Loop through all registered event names/patterns
    for pattern in subscribers:
        # Check if this pattern has a wildcard (*)
        if "*" in pattern:
            # Check if our event matches this pattern
            if matches_wildcard(event_name, pattern):
                # Call all functions subscribed to this pattern
                for callback in subscribers[pattern]:
                    callback(data)
                    notify_count += 1
    
    # Tell the user how many people got notified
    print(f"Published '{event_name}' to {notify_count} subscriber(s)")


def matches_wildcard(event_name, pattern):
    """
    Check if an event name matches a wildcard pattern.
    
    This function handles patterns with asterisks (*).
    
    Args:
        event_name: The actual event (e.g., "user_login")
        pattern: The pattern to match (e.g., "user.*")
    
    Returns:
        True if the event matches, False otherwise
    
    Examples:
        matches_wildcard("user_login", "user.*")      # True
        matches_wildcard("user_logout", "user.*")     # True
        matches_wildcard("payment_success", "user.*") # False
        matches_wildcard("anything", "*")             # True
    """
    # "*" by itself matches everything
    if pattern == "*":
        return True
    
    # Split the pattern into before and after the *
    # Example: "user.*" becomes ["user.", ""]
    parts = pattern.split("*")
    
    # Get the prefix (everything before the *)
    # Example: "user.*" has prefix "user."
    prefix = parts[0]
    
    # Get the suffix (everything after the *)
    # If there's nothing after *, suffix is empty string
    suffix = parts[1] if len(parts) > 1 else ""
    
    # Check if event_name starts with prefix AND ends with suffix
    return event_name.startswith(prefix) and event_name.endswith(suffix)


def get_subscriber_count(event_name=None):
    """
    Count the number of subscribers.
    
    Args:
        event_name: Optional - if given, count subscribers to this event
                             if None, return total count
    
    Returns:
        Number of subscribers
    """
    if event_name is None:
        # Count all subscribers across all events
        total = 0
        for event in subscribers:
            total += len(subscribers[event])
        return total
    else:
        # Count for a specific event
        if event_name in subscribers:
            return len(subscribers[event_name])
        else:
            return 0


# ========================================================================
# DEMO - Run this file to see the system in action!
# ========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PUB-SUB EVENT SYSTEM DEMO")
    print("=" * 70)
    
    # Define some handler functions
    # These are callback functions that run when events are published
    
    def on_user_login(data):
        # This runs when "user_login" event is published
        print(f"  → Login handler: User '{data['username']}' logged in")
    
    def on_user_logout(data):
        # This runs when "user_logout" event is published
        print(f"  → Logout handler: User '{data['username']}' logged out")
    
    def on_any_user_event(data):
        # This runs for ANY event starting with "user_"
        # (because we subscribe to "user.*")
        print(f"  → Wildcard handler caught event: {data}")
    
    def on_payment_event(data):
        # This runs for ANY event starting with "payment_"
        print(f"  → Payment handler: ${data['amount']} {data['currency']}")
    
    # Step 1: Subscribe to events
    print("\n1. SETTING UP SUBSCRIPTIONS:")
    print("-" * 70)
    subscribe("user_login", on_user_login)
    subscribe("user_logout", on_user_logout)
    subscribe("user.*", on_any_user_event)        # Wildcard subscription
    subscribe("payment.*", on_payment_event)      # Wildcard subscription
    
    # Step 2: Publish some events
    print("\n2. PUBLISHING EVENTS:")
    print("-" * 70)
    
    print("\nPublishing 'user_login' event:")
    publish("user_login", {"username": "alice"})
    # This calls both on_user_login AND on_any_user_event (wildcard match!)
    
    print("\nPublishing 'user_logout' event:")
    publish("user_logout", {"username": "bob"})
    # This calls both on_user_logout AND on_any_user_event (wildcard match!)
    
    print("\nPublishing 'payment_success' event:")
    publish("payment_success", {"amount": 50.00, "currency": "USD"})
    # This calls on_payment_event (matches "payment.*")
    
    print("\nPublishing 'payment_failed' event:")
    publish("payment_failed", {"amount": 100.00, "currency": "EUR"})
    # This calls on_payment_event (matches "payment.*")
    
    # Step 3: Show statistics
    print("\n3. SUBSCRIBER STATISTICS:")
    print("-" * 70)
    print(f"Total subscribers: {get_subscriber_count()}")
    print(f"Subscribers to 'user.*': {get_subscriber_count('user.*')}")
    print(f"Subscribers to 'user_login': {get_subscriber_count('user_login')}")
    
    # Step 4: Unsubscribe from an event
    print("\n4. UNSUBSCRIBING:")
    print("-" * 70)
    unsubscribe("user_login", on_user_login)
    
    print("\nPublishing 'user_login' again:")
    publish("user_login", {"username": "charlie"})
    # Now it only calls on_any_user_event (one fewer subscriber)