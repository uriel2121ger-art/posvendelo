"""
Sound Manager - Audio feedback for POS actions
Provides sound effects for add, remove, error, success events
"""

import logging
import os
from pathlib import Path

from PyQt6 import QtCore

# Try to import QtMultimedia - make it optional
try:
    from PyQt6 import QtMultimedia
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False
    # Use a more specific warning for the user
    print("WARNING: QtMultimedia not available. Sound effects will be disabled. "
          "Please ensure PyQt6-Multimedia is installed if you need sound.")

logger = logging.getLogger(__name__)

class SoundManager(QtCore.QObject):
    """Manages sound effects for the application."""
    
    def __init__(self, assets_dir: Path):
        super().__init__()
        self.assets_dir = assets_dir
        self.sounds_enabled = MULTIMEDIA_AVAILABLE
        self.sounds = {}
        
        if not MULTIMEDIA_AVAILABLE:
            logger.warning("Sound system disabled - QtMultimedia not installed or available.")
            return
            
        try:
            self.audio_output = QtMultimedia.QAudioOutput()
            self.audio_output.setVolume(0.5)  # 50% volume
            self._load_sounds()
        except Exception as e:
            logger.warning(f"Could not initialize sound system: {e}")
            self.sounds_enabled = False
            
    def _load_sounds(self):
        """Load sound files from assets directory."""
        if not self.sounds_enabled:
            return
            
        sound_files = {
            'add': 'beep_add.wav',
            'remove': 'beep_remove.wav',
            'error': 'beep_error.wav',
            'success': 'beep_success.wav',
        }
        
        sounds_dir = self.assets_dir / 'sounds'
        if not sounds_dir.exists():
            logger.warning(f"Sounds directory not found: {sounds_dir}")
            self.sounds_enabled = False
            return
            
        for key, filename in sound_files.items():
            filepath = sounds_dir / filename
            if filepath.exists():
                try:
                    effect = QtMultimedia.QSoundEffect()
                    effect.setSource(QtCore.QUrl.fromLocalFile(str(filepath)))
                    self.sounds[key] = effect
                except Exception as e:
                    logger.warning(f"Failed to load sound '{filename}': {e}")
            else:
                logger.warning(f"Sound file not found: {filepath}")
        
        if not self.sounds:
            logger.warning("No sound effects were loaded. Sound system disabled.")
            self.sounds_enabled = False
            
    def play(self, sound_type: str) -> None:
        """Play a sound effect."""
        if not self.sounds_enabled or sound_type not in self.sounds:
            return
        try:
            self.sounds[sound_type].play()
        except Exception as e:
            print(f"Sound playback error: {e}")
            
    def play_beep(self) -> None:
        """Play a simple beep (product added)."""
        self.play('beep')
        
    def play_success(self) -> None:
        """Play success sound (sale completed)."""
        self.play('success')
        
    def play_error(self) -> None:
        """Play error sound."""
        self.play('error')
        
    def play_cash_register(self) -> None:
        """Play cash register sound (payment)."""
        self.play('cash_register')
        
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sounds."""
        self.enabled = enabled
        
    def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)."""
        self.audio_output.setVolume(max(0.0, min(1.0, volume)))

# Global instance - will be initialized by main app with proper assets path
sound_manager = None
