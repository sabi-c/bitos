class AudioPipeline:
    """Stub — full implementation pending."""
    def __init__(self, *args, **kwargs): pass
    def start_recording(self): pass
    def stop_and_process(self): pass
    def cancel(self): pass
    def on_state_change(self, cb): pass
    @property
    def state(self): return "idle"
