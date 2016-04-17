# twitchchat

cfg.py exists in the same directory and is called via import cfg to utilize the below parameters. Substitute your own values.

#config
HOST = "irc.twitch.tv"
PORT = 6667
NICK = "BOT_USERNAME"
PASS = "oauth:abc1234515314532" #chat_login scope at least
CHANNEL = "#riotgames" #channel of interest
RATE = (10/30)
client_id = "client_id"
client_secret = "client_secret" #todo use for looking up channel info to determine game being played
dbname = "postgresql_db_name"
user = "postgres_db_username"
