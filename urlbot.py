#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License version 2 for
# more details.
#
# You should have received a copy of the GNU General Public License version 2
# along with this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import socket
import time
import re
import urllib2
import htmlentitydefs
from threading import *
from BeautifulSoup import BeautifulSoup
import os
import sys
import datetime
import requests
import json
import sqlite3
import random
import bitly_api
from py_expression_eval import Parser


html_pattern = re.compile("&(\w+?);")
html_pattern2 = re.compile("&#([0-9]+);")

def date():
    return datetime.datetime.now().isoformat()

def myprint(str):
    print "%s: %s" % (date(), str)
    sys.stdout.fileno()

def html_entity_decode_char(m):
    try:
        return unicode(htmlentitydefs.entitydefs[m.group(1)], "latin1")
    except KeyError:
        return m.group(0)

def html_entity_decode(string):
    return html_pattern2.sub(lambda x: unichr(int(x.group(1))), html_pattern.sub(html_entity_decode_char, string))
#sql connector class

#end sql connector class

class Shorten:
  def __init__(self,token,url):
    self.token=token
    self.url=url
  def bitly(self):
    try:
      return bitly_api.Connection(access_token=self.token).shorten(self.url)['url']
    except:
      type, value, tb = sys.exc_info()
      myprint("Exception in Shorten::Bitly: %s: %s" % (type, value))
      return None
  def google(self):
    apiurl = "https://www.googleapis.com/urlshortener/v1/url?key=%s" % self.token
    body = {'longUrl': self.url}
    headers = {'Content-type': 'application/json'}
    try:
     r = requests.post(apiurl, data=json.dumps(body), headers=headers)
     if r.status_code > 400:
       myprint("error with shorturl: %s %s" % (r.status_code, r.content))
     else:
       j = r.json()
       return j['id']
     return None
    except:
     return None

class DBConnector:
  def __init__(self, shorturl, url, src, to, dbfile=None, mysql=None):
    self.dbfile=dbfile
    self.mysql=mysql
    self.url=url
    self.to=to
    self.src=src
    self.thread=Thread(target=self.run)
    self.shorturl=shorturl

  def start(self):
    self.db = sqlite3.connect(self.dbfile)
    self.thread.start()

  def join(self):
    self.thread.join()

  def test(self):
    return self.thread.is_alive()

  def run(self):
    if self.dbfile is not None:
      try:
	c = self.db.cursor()
	c.execute('''create table if not exists urlbot (date text, shorturl text, longurl text, chan text, nick text)''')
	db.commit()
	c.execute('''insert into urlbot(date,shorturl,longurl,chan,nick) values (?,?,?,?,?)''', (date(), self.shorturl, self.url, self.to, self.src))
	db.commit()
      except: 
	type, value, tb = sys.exc_info()
	myprint("Error adding url to database: %s: %s" % (type, value.message))
   

class Sender(object):
  def __init__(self, urlbot, src, to, url, at_time, dbfile, bitly):
    self.thread = Thread(target=self.process)
    self.to = to
    self.url = url
    self.urlbot=urlbot
    self.at_time=at_time
    self.bitly=bitly
    self.dbfile=dbfile
    self.src=src

  def start(self):
    self.thread.start()

  def join(self):
    self.thread.join()

  def test(self):
    return self.thread.is_alive()
    
  def process(self):
    while time.time() < self.at_time:
        time.sleep(1)
    myprint("process %r" % self.url)
    try:
	r = urllib2.Request(self.url)
	r.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0')
        soup = BeautifulSoup(urllib2.urlopen(r).read(self.urlbot.max_page_size))
        if soup.title:
           if len(soup.title.string) > self.urlbot.title_length:
    	       title=soup.title.string[0:self.urlbot.title_length] + u'…'
	   else:
	       title=soup.title.string
        else:
    	   title = "Untitled"
    except urllib2.HTTPError as e:
        myprint("HTTPError when fetching %s : %s\n" % (e.url, e))
        return
    except:
        type, value, tb = sys.exc_info()
	myprint("Exception when retreiving title: %s: %s"% (type, value))

    try:
	shorturl = Shorten(self.bitly,self.url).bitly()
	if shorturl is None:
	  return

        title = "%s (%s)" % (shorturl, title)

	self.urlbot.say(self.to, html_entity_decode(title.replace('\n', ' ').strip()))

	DBConnector(shorturl, self.url, self.src, self.to, dbfile=self.dbfile).start()
	
    except:
        type, value, tb = sys.exc_info()
	myprint("Exception in Sender::Process: %s: %s" % (type, value))
    

	# end link shorten



class UrlBot(object):
  def __init__(self, network, chans, nick, port=6667, debug=0, title_length=300, max_page_size=1048576, irc_timeout=360.0, message_delay=3, charset='utf-8', nickserv_pass=None, dbfile=None, mysql=None, bitly=None, prefer_ipv6=False, source_addr=('',0)):
    self.chans=chans
    self.nick=nick
    self.title_length=title_length
    self.max_page_size=max_page_size
    nick_int=0
    nick_bool=False
    nick_next=0
    connected=False
    self.charset=charset
    self.irc=None
    self.idler=None
    self.M=None
    self.debug=debug
    self.last_message=0
    self.networkidx=0
    self.message_delay=message_delay
    self.dbfile=dbfile
    self.mysql=mysql
    self.bitly=bitly
    
    self.url_regexp=re.compile("""((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""")
    self.math_regexp=re.compile(":\d")
    
    while True:
      try:
       for net in network:
	myprint("Looking up %s" % net)
        info = socket.getaddrinfo(net, port)
        ipvx = list([filter((lambda x: x[0] == 10), info), filter((lambda x: x[0] == 2), info)])
        srv = ipvx[0][0] if (len(ipvx[0]) and prefer_ipv6) else ipvx[1][0]

        myprint("Connecting to irc %s" % srv[4][0] )
  	self.irc = socket.create_connection( srv[4][:2], irc_timeout, source_addr ) 
	
        self.send ( u'USER %s %s %s :hello there' % (nick,nick,nick) )
        self.send ( u'NICK %s' % nick )
        while True:
          data = self.irc.recv ( 4096 )
          if len(data)==0:
            break
          data = data.split("\n")
          for data in data:
            if self.debug!=0:
              try:
                myprint(data)
              except:
                pass
            data_split=data.split(' ', 4)
            if len(data_split)>1:
              code=data_split[1]
            else:
              code=0

            if data.find ( b'PING' ) != -1:
              self.irc.send ( b'PONG ' + data.split() [ 1 ] + b'\r\n' )

            if code in [ '004', '376' ] and not connected:
               connected=True
               if nickserv_pass:
                    self.say(u'nickserv',u'IDENTIFY %s' % nickserv_pass)
                    time.sleep(0.5)
               for chan in self.chans:
                 myprint(u"Join %r" % chan)
                 self.send (u'JOIN %s' % chan )
            elif code=='433': # Nickname is already in use
              if not connected:
                self.send ( u'NICK %s%s' % (nick,nick_int) )
                nick_int+=1
              else:
                  nick_next=time.time() + 10
              nick_bool=True
            elif code=='INVITE':
              chan=unicode(data.split(':',2)[2].strip(), self.charset)
              myprint("Invited on %s." % chan)
              if chan.lower() in [ chan.lower().split(' ', 1)[0].strip() for chan in self.chans]:
                myprint(u"Join %r" % chan)
                self.send (u'JOIN %s' % chan )
            elif code=='PRIVMSG':
                dest=data_split[2]
                src=data_split[0].split('!', 1)[0][1:]
                if dest.startswith('#'):
                    to=dest
                    to=unicode(to, self.charset)
                    
                    for url in re.findall(self.url_regexp, data):
                        url=url[0]
                        if not url.startswith('http'):
                            url='http://'+url
                        Sender(self, src, to, url, self.last_message, self.dbfile, self.bitly).start()
                        self.last_message = max(time.time(), self.last_message) + self.message_delay
		    
                    m = re.match(self.math_regexp,data_split[3])
		    if m is not None:
		      try:
		        parser = Parser()
		        x = parser.parse(data_split[3].split(':')[1]).evaluate({})
		        self.say(to, x)
		      except:
		        myprint("Exception parsing math")

            if connected:
              if nick_bool and time.time() > nick_next:
                self.send ( u'NICK %s' % nick )
                nick_bool=False
      except (KeyboardInterrupt,):
	myprint("KeyboardInterrupt detected, raising...")
	raise
      #except:
      #  type, value, tb = sys.exc_info()
      #  myprint("Exception in Urlbot::Init: %s: %s" % (type, value))

      finally:
        if self.irc:
            try: self.irc.close()
            except: pass
        connected=False
        time.sleep(2)

  def say(self,chan,str):
    msg=u'PRIVMSG %s :%s\r\n' % (chan,str)
    if self.debug!=0: myprint(msg.encode(self.charset))
    self.irc.send (msg.encode(self.charset))
  def notice(self,chan,str):
    msg=u'NOTICE %s :%s\r\n' % (chan,str)
    if self.debug!=0: myprint(msg.encode(self.charset))
    self.irc.send (msg.encode(self.charset))
  def send(self,str):
    msg=u'%s\r\n' % (str)
    if self.debug!=0: myprint(msg.encode(self.charset))
    self.irc.send (msg.encode(self.charset))
  


if __name__ == '__main__' :
  import sys
  import os
  import imp

  params_name = UrlBot.__init__.func_code.co_varnames[:UrlBot.__init__.func_code.co_argcount][1:]
  default_args = UrlBot.__init__.func_defaults
  argc = len(params_name) - len(default_args)
  params = dict([(params_name[i], None if i < argc else default_args[i - argc]) for i in range(0, len(params_name))])

  def get_param(str):
    ret = None
    if str in sys.argv:
      i = sys.argv.index(str)
      if len(sys.argv)>i:
         ret = sys.argv[i+1]
         del(sys.argv[i+1])
      del(sys.argv[i])
    return ret

  def check_params(arg):
    if params[arg]: return None
    else: raise ValueError("Parameter %s is mandatory" % arg)

  confdir = get_param('--confdir') or os.path.dirname(os.path.realpath(__file__))
  pidfile = get_param('--pidfile')

  if len(sys.argv)>1:
    module = imp.load_source('config', confdir + "/" + sys.argv[1])
    params.update(module.params)

  try:
    map(check_params, params_name[:argc])
  except (ValueError,) as error:
    sys.stderr.write("%s\n" % error)
    exit(1)

  if pidfile:
    f = open(pidfile, 'w')
    f.write(os.getpid())
    f.close()

  try:
    UrlBot(**params)
  except (KeyboardInterrupt,):
    myprint("Keyboard interrupt received, exiting.")
    exit(0)

