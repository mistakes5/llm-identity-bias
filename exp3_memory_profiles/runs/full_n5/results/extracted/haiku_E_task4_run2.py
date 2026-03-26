# Event System - A publish-subscribe system with wildcard support

class EventBus:
    def __init__(self):
        # Dictionary to store all subscriptions
        # Key: event name (string), Value: list of callbacks
        self.subscribers = {}

    def subscribe(self, event_name, callback):
        """Subscribe a callback function to an event"""
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(callback)
        return callback

    def unsubscribe(self, event_name, callback):
        """Remove a callback from an event"""
        if event_name in self.subscribers:
            try:
                self.subscribers[event_name].remove(callback)
            except ValueError:
                print('Warning: callback not found')
            if len(self.subscribers[event_name]) == 0:
                del self.subscribers[event_name]

    def publish(self, event_name, data=None):
        """Publish an event and notify all subscribers"""
        if data is None:
            data = {}
        
        callbacks_called = 0
        
        # Call direct subscribers
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                callback(data)
                callbacks_called += 1
        
        # Call wildcard subscribers
        wildcard_count = self._call_wildcard_subscribers(event_name, data)
        return callbacks_called + wildcard_count

    def _call_wildcard_subscribers(self, event_name, data):
        """Call any subscribers using wildcard patterns"""
        callbacks_called = 0
        
        for pattern, callbacks in self.subscribers.items():
            if '*' in pattern:
                if self._pattern_matches(pattern, event_name):
                    for callback in callbacks:
                        callback(data)
                        callbacks_called += 1
        
        return callbacks_called

    def _pattern_matches(self, pattern, event_name):
        """
        Check if a wildcard pattern matches an event name.
        
        Examples:
            'user.*' should match 'user_login' -> True
            'user.*' should NOT match 'admin_login' -> False
            '*' should match anything -> True
        
        YOUR TASK: Implement this method!
        HINT: Use Python's fnmatch module for pattern matching
        """
        # TODO: Students implement this!
        pass

    def get_subscription_count(self, event_name=None):
        """Count how many subscribers we have"""
        if event_name is None:
            # Count total across all events
            return sum(len(cbs) for cbs in self.subscribers.values())
        return len(self.subscribers.get(event_name, []))

    def list_events(self):
        """List all subscribed events"""
        return list(self.subscribers.keys())


# Example usage
if __name__ == '__main__':
    bus = EventBus()

    def on_login(data):
        print('User ' + data['username'] + ' logged in')

    def on_any_event(data):
        print('EVENT: ' + str(data))

    # Subscribe to events
    bus.subscribe('user_login', on_login)
    bus.subscribe('*', on_any_event)

    # Publish events
    bus.publish('user_login', {'username': 'alice'})
    
    print('Total subscriptions: ' + str(bus.get_subscription_count()))

from fnmatch import fnmatch
fnmatch('user_login', 'user_*')  # Returns True
fnmatch('admin_login', 'user_*')  # Returns False