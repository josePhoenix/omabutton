# The Oma Button

Use a Raspberry Pi to create an extremely simple interface for listening to
audio files from a flash drive. Three physical buttons are wired up to the
Raspberry Pi's GPIO pins, and the `player.py` script is started on boot to
listen for events from those buttons to control playback. Media files are loaded
from the root folder of a USB flash drive and played in alphabetical order.
(This allows the interested maintainer some control over the ordering of the 
media for playback.)

The player announces the title of the media item before playing, as determined
by either the ID3 tags for title and performer (if present) or the filename
minus any leading numbers.

## Configurable bits

These are all module-level constants in `player.py`.

  * **MEDIA\_ROOT** - set to the mountpoint of the USB flash drive
  * **SPEECH\_HELPER** - a command accepting as an argument a string to be
    spoken through text-to-speech (`say` on the Mac, `flite` on Linux)
  * **BUTTON\_PREVIOUS** - GPIO pin to which the "previous" button is attached
  * **BUTTON\_PLAYPAUSE** - GPIO pin to which the "play/pause" button is
    attached
  * **BUTTON\_NEXT** - GPIO pin to which the "next" button is attached

## Circuitry bits

The GPIO interface code initializes the pins as "pulled-down", meaning that to
register a change when the button is depressed it must provide a path from a
higher voltage to the pin. There's an unspecified (~50k Ohm?) pull resistance
inside the chip the GPIO pins connect to, so you can omit a resistor as long as
the GPIO pins are initialized with a pull-up or pull-down resistor in software
(as they are in `player.py`).

    3v3 |-----o/ o-----| GPIO
             button

## Setting up

Starting from a fresh Raspbian Wheezy image, a few things need to be set up:

  1. Install VLC -- `sudo apt-get install vlc`
  3. Install `supervisor` -- `sudo apt-get install supervisor`
  2. Install the `player.py` script (and dependencies) somewhere

         # mkdir /usr/local/omabutton
         # cd /usr/local/omabutton
         # git clone https://github.com/josePhoenix/omabutton.git
         # ln -s /usr/local/omabutton/omabutton.conf /etc/supervisor/conf.d/omabutton.conf
         # ln -s /usr/local/omabutton/omabutton_logrotate /etc/logrotate.d/omabutton

  #. install flite and any voices, verify it can speak
  5. (optional) Install `anacron` to ensure missed log rotations happen when
     the Pi notices. (This is good if you want a mostly unattended appliance
     without filling up limited SD card storage.)
  6. Ensure your USB drive is mounted automatically and at the same mountpoint
     each time ([these directions](http://www.raspberrypi.org/forums/viewtopic.php?f=27&t=31193#p282044) may help)
     make /media/usbflash
     blkid to get the UUID
     add to /etc/fstab
         UUID=88E5-C60A /media/usbflash/ auto defaults,auto,umask=000,users,rw 0 0
  #. OR just install usbmount and be done with it
  7. Fill your USB drive with media and connect it
  8. Connect your speakers and button hardware
  9. Restart the Raspberry Pi

## Thanks

To Ned Batchelder for [ID3 Reader](http://nedbatchelder.com/code/modules/id3reader.html), and to the VLC
team for making embedding a media player in Python *easier* than shelling out
to a command line MP3 player.

## License

This README and `player.py` are distributed under the terms of the 2-clause BSD
License.

    Copyright (c) 2014, Joseph D. Long
    All rights reserved.

    Redistribution and use in source and binary forms, with or without 
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, 
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
    LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

For licensing information for `vlc.py` and `id3reader.py`, see the headers of
those files.
