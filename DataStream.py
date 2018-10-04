"""
Adam Cummings - Msc Project and Dissertation
"Building an automated cryptocurrency trading bot, a.k.a 'RoBit'"
Data Stream Module

* If you want to run this code, ensure that you have created an appropriate MySQL database
  and filled in the login details found on line 63 *

* Additionally, please retrieve your own personal API key and insert it at line 29 *

"""

import time
import urllib.request
import requests
from urllib.request import urlopen
import json
from pprint import pprint
import datetime
import pymysql.cursors




#################################################################################

#								 Class GetNewData

#################################################################################




# Class gets latest API data from CoinAPI
# Data is stored in json format
class GetNewData:

	url = 'https://rest.coinapi.io/v1/ohlcv/BITSTAMP_SPOT_BTC_USD/'
	apikey = ""
	headers = {'X-CoinAPI-Key' : apikey}

	def __init__(self, command, time_frame):

		if (command == "update"):
			self.api_url = self.url + 'latest?period_id=%s&limit=200'%(time_frame)

		elif (command == "latest"):
			self.api_url = self.url + 'latest?period_id=%s&limit=1'%(time_frame)


		response = requests.get(self.api_url, headers=self.headers)
		data = response.json()

		print(response, command)

		with open("%s.json"%(time_frame),"w") as write_file:
			json.dump(data, write_file)





#################################################################################

#								 Class ImportToMySQL

#################################################################################





# Class formats json file and stored candlestick data in MySQL database for DM use
class ImportToMySQL:

	connection = pymysql.connect(host="", user="", password="",db="",charset="utf8mb4",cursorclass=pymysql.cursors.DictCursor)
	c = connection.cursor()

	def __init__(self, time_frame):

		with open("%s.json"%(time_frame)) as f:
			data = json.load(f)

		for x in data:

			Time_Start = x.get("time_period_start")
			Time_End = x.get("time_period_end")
			Time_Open = x.get("time_open")
			Time_Close = x.get("time_close")
			Price_Open = x.get("price_open")
			Price_High = x.get("price_high") 
			Price_Low = x.get("price_low")
			Price_Close = x.get("price_close") 
			Volume_Traded = x.get("volume_traded") 
			Trades_Count = x.get("trades_count")

			Time_Start = Time_Start[:10] + " " + Time_Start[11:19]
			Time_End = Time_End[:10] + " " + Time_End[11:19]
			Time_Open = Time_Open[:10] + " " + Time_Open[11:19]
			Time_Close = Time_Close[:10] + " " + Time_Close[11:19]

			if (time_frame == "1DAY"):
				entry = "DAYS"
			elif (time_frame == "1HRS"):
				entry = "HOURS"
			elif (time_frame == "7DAY"):
				entry = "WEEKS"
			elif(time_frame == "1MTH"):
				entry = "MNTHS"
			else:
				entry = time_frame

			try: 
				self.c.execute("""INSERT INTO BTC_USD_%s"""%(entry) + """ (Time_Start, Time_End, Time_Open, Time_Close, Price_Open, Price_High, Price_Low, Price_Close, Volume_Traded, Trades_Count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""", (Time_Start, Time_End, Time_Open, Time_Close, Price_Open, Price_High, Price_Low, Price_Close, Volume_Traded, Trades_Count))
			except pymysql.err.IntegrityError as err:
				continue

		self.connection.commit()



