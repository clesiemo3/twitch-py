import sys
import requests
import cfg
import socket
import re
import datetime
import psycopg2
import select
from time import sleep

def socket_start():
	s = socket.socket()
	s.connect((cfg.HOST,cfg.PORT))
	s.send("PASS {}\r\n".format(cfg.PASS).encode("utf-8"))
	s.send("NICK {}\r\n".format(cfg.NICK).encode("utf-8"))
	for chn in cfg.CHANNEL:
		s.send("JOIN {}\r\n".format(chn).encode("utf-8"))

	channelIndex = len(cfg.CHANNEL)-1
	print("Entering prep loop")
	while True:
		response = s.recv(1024).decode("utf-8") #check our socket for data
		print(response)
		if response == "PING :tmi.twitch.tv\r\n":
			s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8")) #respond to PINGs with PONG to keep the socket alive
			print("Pong!")
		#wait until we get an End of /NAMES list response for our channels
		elif re.search(cfg.CHANNEL[channelIndex] + " :End of /NAMES list",response):
			print("Entering main loop and beginning logging...")
			break
	return s

def db_start():
	con = None

	try:
		con = psycopg2.connect("dbname='twitchchat' user='twitch'")
		return con
	except psycopg2.DatabaseError as e:

		if con:
			con.rollback()

		print('Error %s' % e)
		sys.exit(1)

def db_write(con,record):
	try:
		cur = con.cursor()
		query = "INSERT INTO chat (id, username, message, channel, game) VALUES (nextval('twitch_id'),%s, %s, %s, %s)"
		cur.execute(query, record)
		con.commit()
		cur.close()

	except psycopg2.DatabaseError as e:
		if con:
			con.rollback()
		print('Error %s' % e)

def refresh_game_list(channels):
	print("refreshing game list...")
	channelDict = dict((chn,'unknown') for chn in channels)
	for chn in channels:
		chn = chn.replace("#","")
		#print(chn)
		try:
			r = sess.get('https://api.twitch.tv/kraken/channels/'+chn,timeout=(10.0,1.0))
			#print(r.json())
			if r.status_code != 200:
				r.raise_for_status()
			channelDict[chn] = r.json()['game']
		except requests.exceptions.ReadTimeout as e:
			print("refresh twitch api timeout")
		except requests.exceptions.HTTPError as e:
			print("Refresh HTTPError:", e.message)
	channelDict['unknown'] = 'unknown'
	print("refresh completed...")
	return(channelDict)

###Setup###
sess = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3)
sess.mount('https://',adapter)
chnDict = refresh_game_list(cfg.CHANNEL)
CHAT_MSG=re.compile(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")
s = socket_start()
con = db_start()
i=0
j=0

###Get to work###

while True:
	i = i + 1
	if i % 250 == 0:
		print('Still alive. Iteration nbr: ' + str(i) + '; Current DateTime: ' + str(datetime.datetime.now()))

	if i % 500 == 0:
		chnDict = refresh_game_list(cfg.CHANNEL)
	
	try:
		response = s.recv(2048).decode('utf-8') #check our socket for data

		#if response == "PING :tmi.twitch.tv\r\n":
		#	s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8")) #respond to PINGs with PONG to keep the socket alive
		#	print("Pong!")
		#else:
		messages = re.split(r"(\n|\r)+", response) #socket can deliver more than 1 message at a time so we need to split it up.
		for msg in messages:
			if re.search(r"\w+", msg):
				username = re.search(r"\w+", msg).group(0) # return the entire match
			else:
				username = "unknown"
			if re.search(r"#\w+",msg):
				channel = re.search(r"#\w+",msg).group(0)
			else:
				channel = "unknown"
			game = chnDict[channel.replace("#","")]
			msg = re.sub('(\t|\r|\n)+','',msg) #kill off pesky whitespace
			message = CHAT_MSG.sub("", msg)
			if msg == "PING :tmi.twitch.tv":
				s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8")) #respond to PINGs with PONG to keep the socket alive
				print("PONG!")
			elif message != "": #we get some empty strings from newline splitting
				# id | username | message | channel | game | create_dt
				db_record = (username, message, channel, game)
				db_write(con,db_record)
				#print(db_record) #for testing
				if i % 250 == 0:
					print('Still have non-empty messages:',db_record)
		if response == "" and j > 10:
			s.shutdown(2)
			s.close()
			print('connection error. restarting...')
			s = socket_start()
			continue
		elif response == "":
			j = j + 1
		else:
			j = 0
		if i % 250 == 0:
			print(response)
		sleep(0.1) #limit by cfg.rate if you're going to post.

	except socket.error as e:
		print('Error %s' % e)
		s.shutdown(2)
		s.close()
		print('connection error. restarting...')
		s = socket_start()
		continue

	except psycopg2.DatabaseError as e:
		if con:
			con.rollback()
		print('DB Error %s' % e)

	except Exception as ex: #don't crash on me!
		print('General Error %s' % ex)
		continue
