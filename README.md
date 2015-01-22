#urlbot

### What this is

This is a IRC bot written in python that get pages title of urls post in a channel and send them to it

### Installation

Look at the imports and install the modules you are missing with pip. Copy the sample config, edit it
to your liking, and run it from the command line. You can also:

```# make install```

### Usage

If you installed the program via the Makefile,
 put config files (usually botname.conf) in ```/etc/urlbot```, one by bot 
(see the sample config file in the directory) and run :
 
 ```$ sudo service urlbot start```
 
 Otherwise or for debugging purpose juste run :
 
 ```$ ./urlbot.py --confdir /path/to/config/dir file.conf```
