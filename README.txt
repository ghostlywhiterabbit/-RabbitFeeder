RABBITFEEDER
Linux Installation Guide
========================

ABOUT
-----

RabbitFeeder is an aviation traffic monitoring and feeder management
application. It displays aircraft received from a local ADS-B decoder,
provides aircraft identification lookup, and includes a live map with
a visual radar sweep.

SYSTEM REQUIREMENTS
-------------------

- Linux Mint or a compatible Ubuntu-based Linux distribution.
- Python 3.10 or newer.
- Internet connection for installation, map tiles and aircraft lookup.
- An ADS-B decoder providing SBS/BaseStation data on TCP port 31003
  at 127.0.0.1.

INSTALLATION
------------

1. Extract the RabbitFeeder-Linux archive.

2. Open the extracted RabbitFeeder-Linux folder.

3. Right-click inside the folder and choose "Open in Terminal".

4. Run:

   chmod +x install.sh
   ./install.sh

5. Allow the installer to create the Python environment and install
   the required dependencies.

6. When installation completes, RabbitFeeder should appear in your
   applications menu.

FIRST LAUNCH
------------

Open RabbitFeeder from the applications menu.

You can also launch it from a terminal with:

   ~/.local/share/RabbitFeeder/run.sh

MAP CONFIGURATION
-----------------

1. Open RabbitFeeder.
2. Select MAP SETTINGS.
3. Choose Light or Dark appearance.
4. Enter your receiver's latitude and longitude.
5. Set the initial map zoom.
6. Save your settings.

The release starts with neutral map coordinates (0, 0).
You must enter your own receiver coordinates.

ADS-B RECEIVER CONNECTION
-------------------------

RabbitFeeder connects to:

   Host: 127.0.0.1
   Port: 31003
   Format: SBS / BaseStation

Your ADS-B decoder must be running locally and configured to provide
SBS/BaseStation output on TCP port 31003.

RabbitFeeder does not include an ADS-B decoder or SDR driver.
You need a separately installed and configured decoder, such as
dump1090 or readsb, connected to your SDR receiver.

If the application reports that it cannot connect, check that:

- Your SDR receiver is connected.
- Your decoder is running.
- The decoder is listening on TCP port 31003.
- The decoder is accepting connections on 127.0.0.1.

AIRCRAFT IDENTIFICATION
-----------------------

RabbitFeeder can use the HexDB online aircraft database to retrieve
aircraft identification information.

An internet connection is required. Lookup results are cached in
your local aircraft database.

MAP AND INTERNET ACCESS
-----------------------

The map uses MapLibre GL JS and OpenFreeMap map services.
An internet connection is required to load the map and map tiles.

TROUBLESHOOTING
---------------

If installation fails, check that Python 3 and the Python venv
support are installed.

On Linux Mint, these packages can be installed with:

   sudo apt update
   sudo apt install python3 python3-venv python3-pip

If Qt WebEngine fails to start, install the available Qt WebEngine
runtime dependencies for your Linux distribution.

If no aircraft appear, verify your local decoder and SBS connection.

DATA AND PRIVACY
----------------

RabbitFeeder stores its configuration and aircraft lookup database
locally in:

   ~/.local/share/RabbitFeeder/

This release does not contain another receiver's saved coordinates,
aircraft database or feeder credentials.

UNINSTALLATION
--------------

Close RabbitFeeder, then run:

   rm -rf ~/.local/share/RabbitFeeder
   rm -f ~/.local/share/applications/rabbitfeeder.desktop

This removes the application, its local configuration and its
aircraft lookup database.

Enjoy RabbitFeeder!
