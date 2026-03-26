event_bus.py
├── @dataclass Subscription   (id, pattern, callback, once)
├── class EventBus
│   ├── subscribe(pattern, callback, *, once=False) → str (UUID)
│   ├── subscribe_once(pattern, callback) → str
│   ├── unsubscribe(subscription_id) → bool
│   ├── publish(event, **payload) → int   ← you'll shape this one
│   ├── clear(pattern=None) → int
│   ├── subscriber_count (property)
│   └── patterns() → list[str]
└── __main__ demo (8 scenarios, all assertions)