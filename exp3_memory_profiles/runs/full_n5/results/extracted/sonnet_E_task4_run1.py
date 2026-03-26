callback(event_name, data)

try:
                callback(event_name, data)
            except Exception as e:
                print(f"  ⚠ Error in {callback.__name__}: {e}")

from event_bus import EventBus

bus = EventBus()

# Subscribe your UI updater to all to-do changes
bus.subscribe("todo.*", refresh_todo_list)

# Then wherever you create a to-do:
bus.publish("todo.created", {"title": task_name})
# The UI updates automatically — no direct connection needed!