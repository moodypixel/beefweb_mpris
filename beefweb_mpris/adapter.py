import math
import urllib.parse
import urllib.request
from mimetypes import guess_type
from typing import Optional

from gi.repository import GLib
from mpris_server import MetadataObj, ValidMetadata
from mpris_server.adapters import MprisAdapter
from mpris_server.base import Microseconds, PlayState, DbusObj, DEFAULT_RATE, RateDecimal, VolumeDecimal, Track, \
    DEFAULT_TRACK_ID
from mpris_server.mpris.compat import get_track_id

from beefweb_mpris.beefweb import Beefweb


class BeefwebAdapter(MprisAdapter):
    def __init__(self, wrapper: Beefweb):
        self.beefweb = wrapper
        super().__init__()

    def metadata(self) -> ValidMetadata:
        try:
            active_item = self.beefweb.active_item
            columns = active_item.columns
            self.beefweb.download_art()
            coverart_name = urllib.parse.quote(columns.album)
            return MetadataObj(
                track_id=get_track_id(active_item.columns.title),
                length=int(self.beefweb.active_item.duration * 1000000),
                art_url=f'file://{GLib.get_user_cache_dir()}/beefweb_mpris/{coverart_name}',
                title=columns.title,
                artists=[columns.artists],
                album=columns.album,
                album_artists=[columns.album_artist],
                disc_no=int(columns.disc_no) if columns.disc_no.isdigit() else 1,
                track_no=int(columns.track_no) if columns.track_no.isdigit() else 1
            )
        except AttributeError as e:
            return MetadataObj(
                track_id=DEFAULT_TRACK_ID
            )

    def get_current_position(self) -> Microseconds:
        try:
            seconds = self.beefweb.state.estimated_position()
            microseconds = int(seconds * 1000000)
            return microseconds
        except AttributeError:
            return 0

    def next(self):
        self.beefweb.client.play_next()

    def previous(self):
        self.beefweb.client.play_previous()

    def pause(self):
        self.beefweb.client.pause()

    def resume(self):
        self.beefweb.client.pause_toggle()

    def stop(self):
        self.beefweb.client.stop()

    def play(self):
        self.beefweb.client.play()

    def get_playstate(self) -> PlayState:
        try:
            playback_state = self.beefweb.state.playback_state
            if playback_state == "playing":
                return PlayState.PLAYING
            elif playback_state == "paused":
                return PlayState.PAUSED
            return PlayState.STOPPED
        except AttributeError:
            return PlayState.STOPPED

    def seek(
            self,
            time: Microseconds,
            track_id: Optional[DbusObj] = None
    ):
        seconds = time / 1000000
        self.beefweb.client.set_player_state(position=seconds)

    def open_uri(self, uri: str):
        mimetype, _ = guess_type(uri)
        self.beefweb.client.play()

    def is_repeating(self) -> bool:
        try:
            if self.beefweb.state.playback_mode.number == 2:
                return True
            else:
                return False
        except AttributeError:
            return False

    def is_playlist(self) -> bool:
        return True

    def set_repeating(self, val: bool):
        if self.beefweb.state.playback_mode.number == 2:
            self.beefweb.client.set_player_state(playback_mode=0)
        else:
            self.beefweb.client.set_player_state(playback_mode=2)
        print(self.beefweb.state.playback_mode.number)

    def set_loop_status(self, val: str):
        if val == "None":
            self.beefweb.client.set_player_state(playback_mode=0)
        elif val == "Track":
            self.beefweb.client.set_player_state(playback_mode=2)
        elif val == "Playlist":
            self.beefweb.client.set_player_state(playback_mode=1)

    def get_rate(self) -> RateDecimal:
        return DEFAULT_RATE

    def set_rate(self, val: RateDecimal):
        pass

    def set_minimum_rate(self, val: RateDecimal):
        pass

    def set_maximum_rate(self, val: RateDecimal):
        pass

    def get_minimum_rate(self) -> RateDecimal:
        pass

    def get_maximum_rate(self) -> RateDecimal:
        pass

    def get_shuffle(self) -> bool:
        try:
            if self.beefweb.state.playback_mode.number == 4:
                return True
            else:
                return False
        except AttributeError:
            return False

    def set_shuffle(self, val: bool):
        if self.beefweb.state.playback_mode.number == 4:
            self.beefweb.client.set_player_state(playback_mode=0)
        else:
            self.beefweb.client.set_player_state(playback_mode=4)

    def get_art_url(self, track: int) -> str:
        self.beefweb.download_art()
        coverart_name = urllib.parse.quote(self.beefweb.active_item.columns.album)
        return f'file://{GLib.get_user_cache_dir()}/beefweb_mpris/{coverart_name}'

    def get_volume(self) -> VolumeDecimal:
        try:
            # volume from beefweb
            current_vol = self.beefweb.state.volume.value
            min_vol = self.beefweb.state.volume.min
            max_vol = self.beefweb.state.volume.max

            # normalized volume (0.0 to 1.0)
            normalized_vol = (current_vol - min_vol) / (max_vol - min_vol)

            if normalized_vol > 0:
                # checks if the player uses dB
                if self.beefweb.state.volume.type == "db":
                    linear_vol = math.exp(normalized_vol * math.log(100)) / 100  # Convert log scale to linear
                else:
                    linear_vol = normalized_vol
            else:
                linear_vol = 0
            if linear_vol > 1.0:
                linear_vol = 1.0
            
            #print("returning volume: ", linear_vol)
            return linear_vol
        
        except AttributeError:
            return 100

    def set_volume(self, val: VolumeDecimal):
        # volume value sent by the mpris client
        #print("Setting volume (linear input): ", val)

        linear_vol = max(0, min(1, val))
        min_vol = self.beefweb.state.volume.min
        max_vol = self.beefweb.state.volume.max

        # check if the player uses dB
        if self.beefweb.state.volume.type == "db":
            if linear_vol > 0:
                log_vol = math.log(linear_vol * 100) / math.log(100)  # Convert linear to log scale
            else:
                log_vol = 0
            new_vol = min_vol + log_vol * (max_vol - min_vol)
        else:
            new_vol = min_vol + linear_vol * (max_vol - min_vol)

        #print(f"Setting player volume: {new_vol}")      
        return self.beefweb.client.set_player_state(volume=new_vol)

    def is_mute(self) -> bool:
        try:
            return self.beefweb.state.volume.is_muted
        except AttributeError:
            return False

    def set_mute(self, val: bool):
        return self.beefweb.client.set_player_state(mute=False)

    def can_go_next(self) -> bool:
        return True

    def can_go_previous(self) -> bool:
        return True

    def can_play(self) -> bool:
        return True

    def can_pause(self) -> bool:
        return True

    def can_seek(self) -> bool:
        return True

    def can_control(self) -> bool:
        return True

    def get_stream_title(self) -> str:
        pass

    def get_previous_track(self) -> Track:
        pass

    def get_next_track(self) -> Track:
        pass
