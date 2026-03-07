from abc import ABC, abstractmethod

class Song(ABC):
    def __init__(self, title, filename):
        self.title = title
        self.filename = filename

    @abstractmethod
    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        """
        Render the song to audio bytes.
        :param tempo_scale: Multiplier for speed (e.g. 1.5 = 50% faster).
        :param pitch_shift: Shift in semitones (e.g. +12 = octave up).
        :return: Audio data as bytes.
        """
        pass
