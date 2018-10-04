"""
Adam Cummings - Msc Project and Dissertation
"Building an automated cryptocurrency trading bot, a.k.a 'RoBit'"
Decision Module

* If you want to run this code, ensure that you have created an appropriate MySQL database
  and filled in the login details found at lines 224-249 *

"""

import pymysql.cursors
from pprint import pprint
import datetime
import time
import numpy as np
from collections import Counter
import operator
import plotly as py
import plotly.graph_objs as go
import itertools
import sys
#DSM Module
import DataStream
import boto3
import csv
import signal
import argparse
import heapq
import botocore
import os








# Parser Commands
parser = argparse.ArgumentParser()
parser.add_argument('--test', '-t', action='store_true')
parser.add_argument('--graph', '-g', action='store_true')
parser.add_argument('--runs', '-r', metavar='runs', type=int)
parser.add_argument('--date', '-d', metavar=('day','month','year','hour'), type=int, nargs=4, default=[20,12,2017,0])
parser.add_argument('--timeframe', '-f', metavar='pick a timeframe', type=str, default="hour")
parser.add_argument('--speed', '-s', metavar='iteration speed', type=int, default=1)
parser.add_argument('--clock', '-c', metavar='clock interval', type=str, default="HOURS")
parser.add_argument('--bulk', '-b', metavar='bulk test', type=int, default=1)
parser.add_argument('--mobile', '-m', action='store_true')
parser.add_argument('--deposit', '-$', metavar='deposit', default=100)
parser.add_argument('--allLines', '-l', action='store_true')
parser.add_argument('--bullruns', '-^', action='store_true')
parser.add_argument('--extra', '-e', action='store_true')
args = parser.parse_args()




# Function for shutting down RoBit
def signal_handler(sig, frame):
	print('\n\n\n\n+++++++++++++++++++\n Exiting Program..')
	print("+++++++++++++++++++\n\n\n Final Values in Dollars ($):", Analysis.testingresults)
	print(" Total Profitable Sales: ", Analysis.allprofits)
	print(" Total Lossable Sales: ", Analysis.alllosses)
	averageResult = 0
	counter = 0
	for i in Analysis.testingresults:
		if (i == 0.0):
			continue
		else:
			averageResult += i
			counter += 1
	try:
		print(" Total Average: ", averageResult / counter)
	except:
		print(" Total Average: Too few results to average..")

	print("\n\n\n\n")
	Analysis.connection.close()
	sys.exit(0)





# Function provides summary details upon shutdown
def getFinalPrint(): 
	try:	
		print("\n Final Values in Dollars ($):", Analysis.testingresults)
		print(" Total Profitable Sales: ", Analysis.allprofits)
		print(" Total Lossable Sales: ", Analysis.alllosses)
		if (Analysis.maxDollars == args.deposit):
			print(" Peak Funds: $%s (Deposit Funds)"%(Analysis.maxDollars))
		else:
			print(" Peak Funds: $%s (sold on: %s)"%(Analysis.maxDollars, Analysis.maxDate))
		if (Analysis.minDollars == args.deposit):
			print(" Lowest Funds: $%s (Deposit Funds)"%(Analysis.minDollars))
		else:
			print(" Lowest Funds: $%s (sold on: %s)"%(Analysis.minDollars, Analysis.minDate))
		averageResult = 0
		counter = 0
		for i in Analysis.testingresults:
			if (i == 0.0):
				continue
			else:
				averageResult += i
				counter += 1
		print("	Total Average: ", averageResult / counter)
	except: 
		print("RoBit shutdown via Mobile Application.")









#################################################################################

#								 Class Clock

#################################################################################








#Class initiates a start date, which can be specified for testing, or unspecified for real-time trading
class Clock:

	#Initiates a start date-time
	def __init__(self, start=datetime.datetime.now()):
		global YY
		global MM
		global DD
		global hh
		global mm
		global ss
		global date_time

		YY = start.strftime("%Y")
		MM = start.strftime("%m")
		DD = start.strftime("%d")
		hh = start.strftime("%H")
		mm = start.strftime("%M")
		ss = 0

		YY = int(YY)
		MM = int(MM)
		DD = int(DD)
		hh = int(hh)
		mm = int(mm)

		date_time = datetime.datetime(YY, MM, DD, hh, mm, 0)
		self.zero_ticks = True





	#Testing - Adds one tick of time for a defined interval 
	#Application - Watches clock until marker is reached (e.g. every 15 mins)
	def clock_tick(self, time_frame):
		global YY
		global MM
		global DD
		global hh
		global mm
		global ss
		global date_time

		if (time_frame == "WEEKS"):
			DD += 7

		if (time_frame == "15MIN"):
			mm += 15
		else:
			pass	
		if (mm == 60 or time_frame == "HOURS"):
			mm = 0
			hh += 1
		else:
			pass		
		if (hh == 24 or time_frame == "DAYS"):
			hh = 0
			DD += 1
		else:
			pass
		if (DD >= 29 or time_frame == "MNTHS"):
			DD = 1
			MM += 1
		if (MM == 13):
			MM = 1
			YY += 1
		
		date_time = datetime.datetime(YY, MM, DD, hh, mm, 0)



	# Clock changes once every 15 minutes
	def real_clock_tick(self, time_frame):
		global date_time
		if (time_frame == "15MIN"):
			# Avoids KeyboardInterruption Error
			for i in range(3600):
				signal.signal(signal.SIGINT, signal_handler)
				time.sleep(1)

			date_time = datetime.datetime.now()
			print()













#################################################################################

#								 Class Analysis

#################################################################################














"""
Analysis class retrieves candlestick data from MySQL database, 
performs technical analysis, produces various decisions and 
forwards info to AWS S3 Bucket to be used by UIM.

"""
class Analysis:

	limit = 192
	lengthofMA = 20
	dollars = args.deposit
	bitcoins = 0
	sellPlaced = True
	buyPlaced = False
	res_broken = []
	sup_broken = []
	support_res_levels = []
	buy = False
	sell = False
	hold = False
	allsells = []
	previousDollars = 0.0
	allprofits = 0
	alllosses = 0
	testingresults = []
	maxDollars = 0
	minDollars = 1000000000
	minDate = ""
	maxDate = ""
	all_sup_breaks = []
	all_res_breaks = []

	connection = pymysql.connect(host="",
							 user="", 
							 password="",
							 db="",
							 charset="utf8mb4",
							 cursorclass=pymysql.cursors.DictCursor)
	c = connection.cursor()


	def __init__(self, time_frame):
		global alltimeHigh
		global currentPrice
		global percentDif

		if (time_frame == "15MIN"):
			percentDif = 0.01
		elif (time_frame == "HOURS"):
			percentDif = 0.01
		elif (time_frame == "DAYS"):
			percentDif = 0.1
		elif (time_frame == "WEEKS"):
			percentDif = 5.0
		elif (time_frame == "MNTHS"):
			percentDif = 10.0

		alltimeHigh = 0.0
		currentPrice = 0.0

		self.time_frame = time_frame
		self.arr_close = []
		self.arr_open = []
		self.arr_times = []
		self.arr_low = []
		self.arr_high = []
		self.candle_colour = []
		self.candlesizes = []
		self.finalMA = []
		self.upperBol = []
		self.lowerBol = []
		self.support_res_levels = []
		self.res_levels = []
		self.sup_levels = []
		self.bullrun_end = []
		self.bullrun_start = []
		self.bullrun_end_time = []
		self.bullrun_start_time = []
		self.previous_res = []
		self.previous_sup = []
		self.market = ""
		self.previousMarket = ""





	# Given one or the other as input, this function simulates Buy and Sell orders
	def order(buy, sell):
		global dollars
		global bitcoins
		global buyPlaced
		global sellPlaced

		if (sell == True and Analysis.buyPlaced == True):
			temp = Analysis.bitcoins * currentPrice

			if (temp > Analysis.previousDollars):
				Analysis.allprofits += 1
			else:
				Analysis.alllosses += 1

			Analysis.dollars = temp
			Analysis.bitcoins = 00.00
			Analysis.sellPlaced = True
			Analysis.buyPlaced = False
			if (args.bulk < 2):
				print("|- - - - - - - - - -SELL ORDER- - - - - - - - - -|")
				print("                -+ New Balances +-")
				print("                   Bitcoins: %s \n                   Dollars: $%s \n"%(Analysis.bitcoins, int(Analysis.dollars)))
			Analysis.allsells.append(Analysis.dollars)
		else:
			pass
			"Trying to sell, but no bitcoins"

		if (buy == True and Analysis.sellPlaced == True):
			Analysis.previousDollars = Analysis.dollars
			Analysis.bitcoins = 1.00 / (currentPrice / Analysis.dollars)
			Analysis.dollars = 00.00
			if (args.bulk < 2):
				print("|- - - - - - - - - -BUY  ORDER- - - - - - - - - -|")
				print("                -+ New Balances +-")
				print("                   Bitcoins: %s\n                   Dollars: $%s \n"%(Analysis.bitcoins, int(Analysis.dollars)))
			Analysis.sellPlaced = False
			Analysis.buyPlaced = True
		else: 
			pass
			"Trying to buy, but no dollars"







	# Retrieves all candlestick data from MySQL database
	# Also defines Bollinger Band values
	def getChartData(self):
		global alltimeHigh
		global currentPrice

		self.arr_close = []
		self.arr_open = []
		self.arr_times = []
		self.arr_low = []
		self.arr_high = []
		self.candle_colour = []
		self.candlesizes = []
		self.finalMA = []
		self.upperBol = []
		self.lowerBol = []
		self.support_res_levels = []
		self.res_levels = []
		self.sup_levels = []
		self.bullrun_end = []
		self.bullrun_start = []
		self.bullrun_end_time = []
		self.bullrun_start_time = []
		self.fibs = []

		time_frame = self.time_frame
		arr_close = self.arr_close
		arr_open = self.arr_open
		arr_high = self.arr_high
		arr_low = self.arr_low
		arr_times = self.arr_times

		#Gets chart data
		if (self.time_frame != "WEEKS"):
			command = "SELECT * FROM (SELECT * FROM BTC_USD_%s WHERE Time_End <= \"%s\" ORDER BY Time_End DESC LIMIT %s) AS temp ORDER BY Time_End ASC;" % (time_frame, date_time, Analysis.limit)
		else:
			command = "SELECT * FROM (SELECT * FROM BTC_USD_%s WHERE Time_End <= \"%s\" ORDER BY Time_End DESC LIMIT %s) AS temp ORDER BY Time_End ASC;" % (time_frame, date_time, 100)

		Analysis.c.execute(command)

		for row in Analysis.c:

			#Collects candlestick data from period
			price_close = row.get('Price_Close')
			price_open = row.get('Price_Open')
			time_end = row.get('Time_End')
			price_low = row.get('Price_Low')
			price_high = row.get('Price_High')

			#Appends values to arrays
			arr_close.append(price_close)
			arr_open.append(price_open)
			arr_times.append(time_end)
			arr_low.append(price_low)
			arr_high.append(price_high)

			#Creates arrays containing Candle Size and Colour
			if (price_close > price_open):
				candlesize = price_close - price_open
				green_candle = True
				self.candle_colour.append(green_candle)
			else:
				candlesize = price_open - price_close
				green_candle = False
				self.candle_colour.append(green_candle)

			self.candlesizes.append(candlesize)

		#Calculates bollinger bands data from period
		for i in range(len(arr_close)):
			MAarray = arr_close[i - Analysis.lengthofMA:i]
			if (len(MAarray) > 0):
				movingAverage = sum(MAarray) / float(len(MAarray))
			else:
				movingAverage = None

			#Gets current moving average for later use
			if (i == Analysis.lengthofMA):
				currentMovingAverage = movingAverage

			if (movingAverage != None):
				self.finalMA.append(movingAverage)
				self.upperBol.append(movingAverage + (np.std(MAarray)*2))
				self.lowerBol.append(movingAverage - (np.std(MAarray)*2))
			else:
				self.finalMA.append(None)
				self.upperBol.append(None)
				self.lowerBol.append(None)

		if (max(self.arr_high) > alltimeHigh):
			alltimeHigh = max(self.arr_high)

		#Gets current price
		currentPrice = arr_close[-1]




	# Function identifies support and resistance levels
	def getSupRes(self):

		support_res_levels = self.support_res_levels
		sup_res_potentials = []
		average = []
		support_res_levels = []
		self.res_levels = []
		self.sup_levels = []


		for a, b in itertools.combinations(self.arr_close, 2):
			PD = Analysis.percentageDiff(a, b)
			average.append(PD)

			if (PD < percentDif):
				sup_res_potentials.append(a)

		sup_res_potentials = Counter(sup_res_potentials)

		#attaches max occurring value to support_res_levels
		if (len(sup_res_potentials) > 0):
			max_freq = sup_res_potentials.most_common(1)
		for key, value in sup_res_potentials.items():
			if (value == max_freq and value > 1):
				support_res_levels.append(key)


		if (len(sup_res_potentials) > 1 and len(support_res_levels) < 2):
			additionalsupres = sup_res_potentials.most_common(1)[-1]
			support_res_levels.append(additionalsupres[0])



		for i in support_res_levels:
			if (currentPrice < i):
				self.res_levels.append(i)
			else:
				self.sup_levels.append(i)




	# Function formats horizontal support and resistance lines on graph
	def createShape(line, linecolour):
		layout = {
			'type' : 'line',
			'x0' : 0,
			'x1' : 1,
			'y0' : line,
			'y1': line,
			'xref' : 'paper',
			'yref' : 'y',
			'line' : {'color' : linecolour, 'width' : 2}
			}
		return layout



	# Function creates graph/ chart (specified with --graph at parser)
	def createChart(self, targetlines1=None, targetlines2=None, targetlines3=None, targetlines4=None, removelines=True, fibon=False):
		title = "Bitcoin/USD Currency Chart - " + self.time_frame

		if (args.allLines == False):
			removals = []
			for a in targetlines1, targetlines2, targetlines3, targetlines4:
				if (a == None):
					continue
				else:
					for index, b in enumerate(a):
						if (Analysis.percentageDiff(b, currentPrice) > 10.0):
							removals.append(index)	
					for byebye in sorted(removals, reverse=True):
						del a[byebye]
					removals = []

		trace1 = go.Candlestick(x=self.arr_times, open=self.arr_open, high=self.arr_high, low=self.arr_low,
				 close=self.arr_close, name='Candlestick',
				 decreasing=dict(line=dict(color= 'rgb(105,105,105)')))

		trace2= go.Scatter(x = self.arr_times, y = self.finalMA, mode = 'lines', name = 'Moving Average')
		trace3= go.Scatter(x = self.arr_times, y = self.upperBol, mode = 'lines', name = 'Upper Bollinger Band', line=dict(color=('rgb(255,69,0)')))
		trace4= go.Scatter(x = self.arr_times, y = self.lowerBol, mode = 'lines', name = 'Lower Bollinger Band', line=dict(color=('rgb(255, 165, 0)')))
		trace5 = go.Scatter(x = self.bullrun_end_time, y = self.bullrun_end, mode = 'markers', name='Bull Run End')
		trace6 = go.Scatter(x = self.bullrun_start_time, y = self.bullrun_start, mode = 'markers', name='Bull Run Start') 


		dataGraph = [trace1, trace2, trace3, trace4, trace5, trace6]

		layout = {
			'title' : '%s' % (title),
			'yaxis' : {'title' : 'Price ($)'},
			'shapes' : [],
		}

		for target in targetlines1, targetlines2, targetlines3, targetlines4:
			if (target == targetlines1 and target != None):
				#Light Blue
				lineColour = 'rgb(135,206,250)'
			elif (target == targetlines2 and target != None):
				#Purple
				lineColour = 'rgb(123,104,238)'
			elif (target == targetlines3 and target != None):
				#Light Green
				lineColour = 'rgb(144,238,144)'
			elif (target == targetlines4 and target != None):
				#Olive
				lineColour = 'rgb(128,128,0)'

			if (target):
				for final in target:
					layout['shapes'].append(Analysis.createShape(final, lineColour))

		if (fibon == True):
			for fib in self.fibs:
				layout['shapes'].append(Analysis.createShape(fib, 'rgb(0,0,0)'))

		fig = dict(data=dataGraph, layout=layout)
		py.offline.plot(fig)




	
	# Gets the percentage difference between two numbers
	def percentageDiff(a, b):
		if (a >= b):
			PD = ((a - b)/a) * 100
		else:
			PD = ((b - a)/b) * 100
		return PD




	# Function identifies bullrun/ bearrun start and end points
	# Also identifies fibonacci numbers (currently unused)
	def findBullRuns(self, getfib=False):
		for index, item in enumerate(self.arr_close):
			if (index != 0):
				if (item < (self.arr_close[index-1])):
					pass
				elif(item > (self.arr_close[index-1]) and self.candlesizes[index] > self.candlesizes[index-1] and self.candle_colour[index-1] == True):
					if (index != self.arr_close.index(self.arr_close[-1])):
						if (item > (self.arr_close[index+1])):
							self.bullrun_end.append(self.arr_low[index+1])
							self.bullrun_end_time.append(self.arr_times[index+1])

							self.bullrun_start.append(self.arr_high[index])
							self.bullrun_start_time.append(self.arr_times[index])
					else:
						pass
				else:
					pass

		# Fibonacci Retracement
		if (getfib == True):
			bull_dict = {}

			for index, item in enumerate(self.bullrun_end):
				bull_dict[item] = self.bullrun_end_time[index]
			for index, item in enumerate(self.bullrun_start):
				bull_dict[item] = self.bullrun_start_time[index]

			order = sorted(bull_dict, key=bull_dict.get)
			alldifs = []

			for index, item in enumerate(order):
				if (index == 0 or index % 2 == 0):
					continue
				else:
					if (index < order.index(order[-1])):
						dif = order[index+1] - item
						fib = ((dif * 0.618) - order[index+1]) * (-1)
						alldifs.append(dif)
						self.fibs.append(fib)





	# Function identifies when support and resistance lines have been broken
	def checkBrokenBands(self):
		target_indices_res = None
		self.res_broken = []
		self.sup_broken = []

		for index, value in enumerate(self.previous_res):
			if (currentPrice >= value):
				target_indices_res = index
				if (args.extra == True):
					print("       ((((((((Resistance line broken)))))))) (%s : %s)"%(self.time_frame,value))
				self.res_broken.append(self.time_frame)
				 

		target_indices_sup = None

		for index, value in enumerate(self.previous_sup):
			if (currentPrice <= value):
				if (args.extra == True):
					print("      ((((((((Support line broken)))))))) (%s : %s)"%(self.time_frame, value))
				self.sup_broken.append(self.time_frame)

		self.previous_sup =  self.sup_levels
		self.previous_res =  self.res_levels




	# Function identifies current and past market
	def getMarket(self):
		self.previousMarket = self.market

		if (currentPrice > self.finalMA[-1] and currentPrice < self.upperBol[-1]):
			self.market = "bull"
		elif (currentPrice > self.finalMA[-1] and currentPrice >= self.upperBol[-1]):
			self.market = "overBull"
		elif (currentPrice < self.finalMA[-1] and currentPrice > self.lowerBol[-1]):
			self.market = "bear"
		elif (currentPrice < self.finalMA[-1] and currentPrice <= self.lowerBol[-1]):
			self.market = "overBear"

		if (args.extra == True):
			print("            Current Market (%s): "%(self.time_frame) + self.market)

		return self.market




	# Within Bollinger bands and at some distance from the all-time high price
	# this function considers resistance and support levels from different time-frames
	def buyORsell(self, mode):

		if (mode == "trade"):

			if (Analysis.percentageDiff(currentPrice, alltimeHigh) < 10.0):
				Analysis.buy = False

			# Check if any support bands have been broken
			if (self.market != "overBull" ):
				if (len(Analysis.all_sup_breaks) > 0):
					Analysis.buy = True
					Analysis.sell = False


			# Checks if any resistances bands have been broken
			if (self.market != "overBear"):
				if (len(Analysis.all_res_breaks) > 0):
					Analysis.sell = True
					Analysis.buy = False


			
		
# Plays a sound when program completes iterations
def beep():
	print("\a")







def main():


	minute15 = Analysis("15MIN")
	hour = Analysis("HOURS")
	day = Analysis("DAYS")
	week = Analysis("WEEKS")
	month = Analysis("MNTHS")

	
	firstTick = True
	datedollarsiter = 0

	"""
	-------------------------------
	Variables that can be changed for testing or running purposes
	currently mostly defined at parser
	-------------------------------
	"""

	if (args.runs):
		runs = args.runs
	else:
		runs = 1

	if (args.test == True):
		testing = True
	else:
		testing = False
		runs = runs * 24

	if (args.graph == True):
		graph = True
	else:
		graph = False

	iters = args.bulk
	sleep = args.speed
	newCSV = True
	ticker = args.clock

	"""
	-------------------------------
	Running Process
	-------------------------------
	"""

	# First For-Loop is used for defining a start time and updating new data from APIs when running in real-time
	for runtime in range(iters):
		global currentPrice
		global alltimeHigh

		currentPrice = 0.0
		alltimeHigh = 0.0



		if (testing == True):
			clock1 = Clock(start=datetime.datetime(args.date[2], args.date[1], args.date[0], args.date[3], 0, 0))
		else:
			clock1 = Clock(start=datetime.datetime.now())

			if (firstTick == True):
				all15MIN = DataStream.GetNewData("update", "15MIN")
				allHOUR = DataStream.GetNewData("update", "1HRS")
				allDAYS = DataStream.GetNewData("update","1DAY")
				allWEEKS = DataStream.GetNewData("update","7DAY")
				allMNTHS = DataStream.GetNewData("update","1MTH")
				firstTick = False
			else:
				all15MIN = DataStream.GetNewData("latest", "15MIN")
				allHOUR = DataStream.GetNewData("latest", "1HRS")
				allDAYS = DataStream.GetNewData("latest","1DAY")
				allWEEKS = DataStream.GetNewData("latest","7DAY")
				allMNTHS = DataStream.GetNewData("latest","1MTH")

			DataStream.ImportToMySQL("15MIN")
			DataStream.ImportToMySQL("1HRS")
			DataStream.ImportToMySQL("1DAY")
			DataStream.ImportToMySQL("7DAY")
			DataStream.ImportToMySQL("1MTH")


		# Second For-Loop range defines how many time-intervals the bot will iterate over
		# For example, if range is set to 100, it will perform all of its actions 100 times over a defined clock interval
		for i in range(runs):



			if (args.bulk > 1):
				plus = "Iteration Number: %s out of %s: " % (runtime+1, iters)
				sys.stdout.write( chr(8) * len(plus) + plus)
				msg = "Completion %i%% " % (i)
				sys.stdout.write(msg + chr(8) * (len(msg)))
				sys.stdout.flush()
				time.sleep(0.02)

			if (args.bulk < 2):
				print("#%s"%(i+1), date_time, "Current Price: $%s"%(currentPrice))

			#  !!! Always order from larger time frames to smaller ones !!!
			# Gets MySQL data
			month.getChartData()
			week.getChartData()
			day.getChartData()
			hour.getChartData()
			# minute15.getChartData()
			

			# Finds support and resistance levels
			day.getSupRes()
			day.checkBrokenBands()

			week.getSupRes()
			week.checkBrokenBands()

			month.getSupRes()
			month.checkBrokenBands()

			Analysis.all_sup_breaks = day.sup_broken + week.sup_broken + month.sup_broken
			Analysis.all_res_breaks = day.res_broken + week.res_broken + month.res_broken

			daylines = day.sup_levels + day.res_levels
			weeklines = week.sup_levels + week.res_levels
			monthlines = month.sup_levels + month.res_levels


			if (args.bullruns == True):
				# hour.findBullRuns(getfib=True)
				day.findBullRuns(getfib=True)
				week.findBullRuns(getfib=True)
				month.findBullRuns(getfib=True)

			# Produces Graph/ Chart
			if (graph == True):
				if (args.timeframe == "day"):
					chosenObject = day
				elif (args.timeframe == "week"):
					chosenObject = week
				elif (args.timeframe == "month"):
					chosenObject = month
				else:
					chosenObject = hour

				chosenObject.createChart(daylines, weeklines, monthlines, removelines=True, fibon=False)


			
			# Defines time frame markets
			day.getMarket()
			week.getMarket()
			month.getMarket()


			# Uses Bollinger Bands to identify potential buy and sell opportunities
			if (day.previousMarket != day.market):
				if (day.previousMarket == "overBull" and day.market == "bull"):
					Analysis.buy = True

				elif (day.previousMarket == "bull" and day.market == "overBull"):
					Analysis.sell = True

				elif (day.previousMarket == "bear" and day.market == "bull"):
					Analysis.sell = True

				elif (day.previousMarket == "bull" and day.market == "bear"):
					Analysis.buy = True

				elif (day.previousMarket == "bear" and day.market == "overBear"):
					Analysis.buy = True

				elif (day.previousMarket == "overBear" and day.market == "bear"):
					Analysis.sell = True


			# Checks sup/ res breakages before making final trade decision
			day.buyORsell("trade")

			# Performs Buy, Sell or neither
			Analysis.order(Analysis.buy, Analysis.sell)


			Analysis.buy = False
			Analysis.sell = False
			Analysis.res_broken = []
			Analysis.sup_broken = []
			daylines = []
			weeklines = []
			monthlines = []

			# End of Analysis

			
			"""
			-------------------------------
			Section Below Uploads Data to Amazon Web Services for App usage
			-------------------------------
			"""


			if (args.mobile == True):
				# Necessary to run this code upon first iteration to create a transferable csv file
				if (datedollarsiter == 0 and newCSV == True):
					a = np.asarray([[date_time, 100]])
					np.savetxt('date_dollars.csv', a, delimiter=",", fmt='%s')
					datedollarsiter += 1
				else:
					datedollarsiter += 1
					fields=[date_time, Analysis.dollars]
					with open(r'date_dollars.csv', 'a') as f:
						writer = csv.writer(f)
						writer.writerow(fields)

				if (args.extra == True):
					print("iteration: ",datedollarsiter)		

				# Currently set to > 6 for demo purposes. This allows the UIM graph to be filled with data quickly
				if (datedollarsiter > 6):
					s3 = boto3.resource('s3')
					s3.meta.client.upload_file('date_dollars.csv', 'simplebucket1234', 'date_dollars.csv')
					if (args.extra == True):
						print("file uploaded to s3 - sleeping..")
					time.sleep(int(17))

					# Checks to see if terminate button was pressed on UIM
					try:
						s3.Object('simplebucket1234', 'terminate.txt').load()
						print("App wants to terminate. Exiting Program...")
						getFinalPrint()
						s3.Object('simplebucket1234', 'terminate.txt').delete()
						Analysis.connection.close()
						exit()
					except botocore.exceptions.ClientError as e:
						if e.response['Error']['Code'] == "404":
							pass
						else:
							"something unexpected has gone wrong"
					else:
						pass
						

			if (Analysis.dollars != 0 and Analysis.dollars > Analysis.maxDollars):
				Analysis.maxDollars = Analysis.dollars
				Analysis.maxDate = date_time
			if (Analysis.dollars != 0 and Analysis.dollars < Analysis.minDollars):
				Analysis.minDollars = Analysis.dollars
				Analysis.minDate = date_time


			# Time change for next run
			if (testing == True):
				clock1.clock_tick(ticker)
			else:
				clock1.real_clock_tick("15MIN")


			#If CTRL-C is pressed to exit program, this method closes MySQL connection before exiting
			signal.signal(signal.SIGINT, signal_handler)

			#intervals of 1 seconds eliminate KeyboardInterruption Error
			for i in range(sleep):
				time.sleep(1)


		# For Bulk-Test Mode, this make a note of final values
		if (Analysis.dollars != 0):
			Analysis.testingresults.append(int(Analysis.dollars))
		else:
			Analysis.testingresults.append(int(Analysis.previousDollars))



		
		Analysis.dollars = args.deposit
		Analysis.bitcoins = 0
		Analysis.sellPlaced = True
		Analysis.buyPlaced = False
		Analysis.res_broken = []
		Analysis.sup_broken = []
		Analysis.support_res_levels = []
		Analysis.buy = False
		Analysis.sell = False
		Analysis.allsells = []
		Analysis.previousDollars = 0.0
		day.market = ""
		week.market = ""
		month.market = ""
		Analysis.alltimeHigh = 0
		Analysis.currentPrice = 0




		args.date[0] += 1

	# End of Loops

	getFinalPrint()
	beep()
	
	Analysis.connection.close()


















#Runs program if DecMod.py is executed
if __name__ == "__main__":
	main()
