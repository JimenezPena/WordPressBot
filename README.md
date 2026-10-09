This repository contains a program that automatically comments new publications in a WordPress blog using the gemini-2.5-flash model to generate the according comment. 
The main code is BotWordPressJuande.py. A list of posts already processed is maintained in post_procesados.json
A secondary script, ScriptObtenerToken.py, needs to be run only once in order to obtain the necessary access token to WordPress (to post the comments in the blog)
