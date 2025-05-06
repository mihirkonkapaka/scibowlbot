# scibowlbot

A Discord Bot that I have created that reads Science Bowl Questions from CQCumber's ScibowlDB Database.
There are only 6 commands this bot supports as of the last commit:
```
/start - starts the game
/end - ends the game
/debug - checks if the bot is running
/a - answers a Short Answer question
/score - checks your score
/help - prints this text
```
In addition, I would suggest having only `1` (one) channel for the bot, as it currently does *not* support multiple instances in multiple channels.

---
If you would like to run your own instance of this bot, make a `.env` file within the folder the script is in. The contents should be as so:
```
DISCORD_TOKEN="Token of the application"
GUILD_ID = "GUILD ID of the server you want to host it in"
```
On the first run of the script, a file named `points.json` should be created, and a `discord.log` may also be added to the directory.
Feel free to host your own instances of this bot, but if you clone/modify the bot and publish it publicly, please credit CQCumber and I.
