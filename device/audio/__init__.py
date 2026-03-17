class AudioPipeline:
    """Stub — full implementation pending."""
    def __init__(self, *args, **kwargs): pass
    def start_recording(self): pass
    def stop_and_process(self): pass
    def cancel(self): pass
    def on_state_change(self, cb): pass
    @property
    def state(self): return "idle"


# Lazy imports — avoid pulling in numpy/pyaudio at module level
def get_shared_stream():
    from audio.shared_stream import SharedAudioStream
    return SharedAudioStream

def get_vad():
    from audio.vad import VoiceActivityDetector
    return VoiceActivityDetector

def get_wake_word_detector():
    from audio.wake_word import WakeWordDetector
    return WakeWordDetector
