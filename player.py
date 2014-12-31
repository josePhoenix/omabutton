#!/usr/bin/env python
import re
import sys
import multiprocessing
import subprocess
import time
import os
import glob
import Queue as queue
import logging

LOG_FORMAT = "%(asctime)s %(module)s:%(lineno)d [%(levelname)s]: %(message)s"

logging.basicConfig(format=LOG_FORMAT, level=logging.WARN)
log = logging  # shorthand

try:
    from RPi import GPIO
    _ON_RASPI = True
except ImportError:
    GPIO = None
    _ON_RASPI = False

import vlc
import id3reader

if _ON_RASPI:
    MEDIA_ROOT = "/media/usb0"
    SPEECH_HELPER = "flite"
else:
    MEDIA_ROOT = "/Users/jdl/dev/omabutton/media"
    SPEECH_HELPER = "say"

BUTTON_PREVIOUS = 25
BUTTON_PLAYPAUSE = 22
BUTTON_NEXT = 4

class Buttons(object):
    def __init__(self, button_names):
        self._lookup = {}
        for identifier, channel_number in button_names.items():
            setattr(self, identifier, channel_number)
            self._lookup[channel_number] = identifier

    def __getitem__(self, channel_number):
        return self._lookup[channel_number]

    def initialize(self, callback):
        GPIO.setmode(GPIO.BCM)
        for channel in self._lookup.keys():
            GPIO.setup(channel, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(
                channel,
                GPIO.FALLING,  # buttons pulled down, so falling
                               # means when button released
                callback=callback,
                bouncetime=1000
            )

class SpeechRequest(object):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    COMPLETED = 2

    def __init__(self, msg):
        self.msg = msg
        self.ref = None
    def play(self):
        self.ref = subprocess.Popen((SPEECH_HELPER, self.msg))
    def wait(self):
        if self.ref is None:
            return
        while self.status() != SpeechRequest.COMPLETED:
            time.sleep(0.2)
    def stop(self):
        if self.ref:
            try:
                self.ref.terminate()
            except OSError as e:
                if e.errno == errno.ESRCH:
                    pass # race condition where pid might be cleaned up before
                         # we try to kill it
                else:
                    raise
    def status(self):
        if self.ref is None:
            return SpeechRequest.NOT_STARTED
        else:
            if self.ref.poll() is None:
                return SpeechRequest.IN_PROGRESS
            else:
                return SpeechRequest.COMPLETED

class Player(multiprocessing.Process):
    media_files = []
    def __init__(self, media_root, buttons):
        self.buttons = buttons
        self.event_queue = multiprocessing.Queue()

        # VLC plumbing
        self._media_root = media_root
        self._instance = vlc.Instance()
        self.now_playing = self._instance.media_player_new()
        self._vlc_event_manager = self.now_playing.event_manager()
        self._vlc_event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._auto_advance
            # proceed to the next item upon finishing one
        )
        self._media_list_position = 0

        self.running = False
        self.media_files = glob.glob(os.path.join(self._media_root, '*.mp3'))
        self.media_files.sort()

        if not len(self.media_files) > 0:
            log.error('Cannot init player! No media '
                     'found in {}'.format(self._media_root))
            sys.exit(1)
        super(Player, self).__init__()

    def _auto_advance(self, *args, **kwargs):
        log.debug('[_auto_advance] event from VLC: {} {}'.format(args, kwargs))
        player.send_event(BUTTON_NEXT)

    @staticmethod
    def _say(message):
        speech = SpeechRequest(message)
        speech.play()
        speech.wait()

    @staticmethod
    def _name_for_media(normpath):
        id3r = id3reader.Reader(normpath)
        if id3r.getValue('title') is not None and \
                id3r.getValue('performer') is not None:
            return '{0} from {1}'.format(
                id3r.getValue('title').encode('ascii', 'ignore'),
                id3r.getValue('performer').encode('ascii', 'ignore')
            )
        else:
            # Fallback on filename parsing
            filename = os.path.basename(normpath).replace('.mp3', '')
            return re.sub(r'\d+\s*-?\s*', '', filename)

    def _begin_media(self, filepath, begin_as_paused=False):
        if self.now_playing.is_playing():
            log.debug('[_begin_media] currently is_playing, stopping before '
                   'switching media')
            self.now_playing.stop()
        normpath = os.path.abspath(filepath)
        log.debug('[_begin_media] attempting to load {}'.format(normpath))
        try:
            media = self._instance.media_new(normpath)
        except NameError:
            log.error('NameError: %s (%s vs LibVLC %s)' % (sys.exc_info()[1],
                                                       __version__,
                                                       libvlc_get_version()))
            sys.exit(1)
        self.now_playing.set_media(media)
        log.debug('[_begin_media] set_media succeeded')
        self._name = self._name_for_media(normpath)
        if not begin_as_paused:
            log.debug('[_begin_media] begin_as_paused not set, playing')
            self.play()

    def play(self):
        log.debug('[play] announcing name: {}'.format(self._name))
        self._say('Now playing: {}'.format(self._name))
        log.debug('[play] begin playing...')
        self.now_playing.play()
        log.debug('[play] ...playing!')

    def pause(self):
        if self.now_playing.is_playing():
            self.now_playing.set_pause(True)

    def playpause(self):
        if not self.now_playing.is_playing():
            log.debug('[playpause] currently not is_playing, play()')
            self.play()
        else:
            log.debug('[playpause] currently is_playing, pause()')
            self.pause()

    def next_media(self):
        self._media_list_position += 1
        if self._media_list_position >= len(self.media_files):
            log.debug('[next_media] wrap around, we reached the end')
            self._media_list_position = 0
        self._begin_media(self.media_files[self._media_list_position])

    def previous_media(self):
        self._media_list_position -= 1
        if self._media_list_position < 0:
            log.debug('[previous_media] wrap around, we reached the beginning')
            self._media_list_position = len(self.media_files) - 1
        self._begin_media(self.media_files[self._media_list_position])

    def send_event(self, event_channel):
        log.debug('[send_event] {}'.format(event_channel))
        self.event_queue.put(event_channel)

    def initialize(self):
        # on first start, load the first media item in the list
        # and set it to paused
        log.debug("[initialize] Queueing up first media item...")
        self._media_list_position = 0
        self._begin_media(self.media_files[0], begin_as_paused=True)
        self._say("Ready to play!")
        log.debug("[initialize] Ready to play!")

    def dispatch(self, event):
        if self.now_playing is None:
            log.debug('[dispatch] Not done initializing yet; '
                      'ignore button press')
            return
        if event == BUTTON_NEXT:
            # cancel currently playing item
            # begin playing next item, wrapping if necessary
            log.debug('[dispatch] got BUTTON_NEXT')
            self.next_media()
        elif event == BUTTON_PLAYPAUSE:
            # pause currently playing item
            log.debug('[dispatch] got BUTTON_PLAYPAUSE')
            self.playpause()
        elif event == BUTTON_PREVIOUS:
            # cancel currently playing item
            # begin playing previous item, wrapping if necessary
            log.debug('[dispatch] got BUTTON_PREVIOUS')
            self.previous_media()
        else:
            log.debug('[dispatch] What? Unknown button: {}'.format(event))

    def run(self):
        self.running = True
        self.initialize()
        while self.running:
            try:
                log.debug('[run] checking for event...')
                event = self.event_queue.get(block=True, timeout=1.0)
                log.debug('[run] got event {} ({})', self.buttons[event], event)
                self.dispatch(event)
            except queue.Empty:
                pass # try again for another second
                     # (prevents waiting forever on quit for a blocking get())

if __name__ == "__main__":
    if _ON_RASPI:
        buttons = Buttons({
            'PREVIOUS': BUTTON_PREVIOUS,
            'PLAYPAUSE': BUTTON_PLAYPAUSE,
            'NEXT': BUTTON_NEXT,
        })
    else:
        buttons = {}
    player = Player(MEDIA_ROOT, buttons)
    if _ON_RASPI:
        buttons.initialize(callback=player.send_event)
    player.start()
    while not _ON_RASPI:
        command = raw_input("---\nnext - n\nplaypause - .\nprevious - p\n> ")
        if not command:
            continue
        elif command[0] == 'n':
            print 'next'
            player.send_event(BUTTON_NEXT)
        elif command[0] == 'p':
            print 'previous'
            player.send_event(BUTTON_PREVIOUS)
        elif command[0] == '.':
            print 'play/pause'
            player.send_event(BUTTON_PLAYPAUSE)
        else:
            print '???'
    # run forever
    player.join()