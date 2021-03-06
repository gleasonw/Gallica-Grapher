import csv
import re
import sys
import shutil
import os
import concurrent.futures

from Backend.GettingAndGraphing.dictionaryMaker import DictionaryMaker
from Backend.GettingAndGraphing.getterOfAllResultsFromPaper import *

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

class GallicaSearch:

	def __init__(self, searchTerm, newspaper, yearRange, strictYearRange, **kwargs):
		self.lowYear = None
		self.highYear = None
		self.isYearRange = None
		self.baseQuery = None
		self.strictYearRange = strictYearRange
		self.totalResults = 0
		self.progressPercent = 0
		self.progressIterations = 0
		self.newspaper = newspaper
		self.newspaperDictionary = {}
		self.chunkedNewspaperDictionary = {}
		self.collectedQueries = []
		self.searchTerm = searchTerm
		self.topPapers = []
		self.topTenPapers = []
		self.numResultsForEachPaper = {}
		self.establishYearRange(yearRange)
		self.parseNewspaperDictionary()
		self.establishStrictness()
		self.buildQuery()

		self.paperNameCounts = []

		self.fileName = self.determineFileName()

	def checkIfFileAlreadyInDirectory(self):
		return os.path.isfile(os.path.join("../CSVdata", self.fileName))

	def runQuery(self):
		if self.checkIfFileAlreadyInDirectory():
			print("File exists in directory, skipping.")
		else:
			self.findTotalResults()
			self.runSearch()

	def getTopTenPapers(self):
		return self.topTenPapers

	def getFileName(self):
		return self.fileName

	def getSearchTerm(self):
		return self.searchTerm

	def getYearRange(self):
		return "{0}-{1}".format(self.lowYear, self.highYear)

	def getCollectedQueries(self):
		return self.collectedQueries

	def getPercentProgress(self):
		return self.progressPercent

	@staticmethod
	def makeSession():
		gallicaHttpSession = sessions.BaseUrlSession("https://gallica.bnf.fr/SRU")
		adapter = TimeoutAndRetryHTTPAdapter(timeout=2.5)
		gallicaHttpSession.mount("https://", adapter)
		gallicaHttpSession.mount("http://", adapter)
		return gallicaHttpSession

	@staticmethod
	def sendQuery(queryToSend, **kwargs):
		session = GallicaSearch.makeSession()
		if kwargs['startRecord'] is None:
			startRecord = 1
		else:
			startRecord = kwargs['startRecord']
		if kwargs['numRecords'] is None:
			numRecords = 50
		else:
			numRecords = kwargs['numRecords']
		hunter = GallicaHunter(queryToSend, startRecord, numRecords, session)
		hunter.hunt()
		return hunter

	def packageQuery(self):
		if len(self.collectedQueries) != 0:
			self.generateTopTenPapers()
			self.makeCSVFile()
		else:
			pass

	def makeCSVFile(self):
		with open(self.fileName, "w", encoding="utf8") as outFile:
			writer = csv.writer(outFile)
			writer.writerow(["date", "journal", "url"])
			for csvEntry in self.collectedQueries:
				writer.writerow(csvEntry)
		shutil.move(self.fileName, os.path.join("../CSVdata", self.fileName))

	def determineFileName(self):
		nameOfFile = ''
		if self.newspaper == "all":
			nameOfFile = self.searchTerm + "-all-"
		else:
			for paper in self.newspaper:
				nameOfFile = paper + "-"
			nameOfFile = nameOfFile[0:len(nameOfFile)-1]
			wordsInQuery = self.searchTerm.split(" ")
			for word in wordsInQuery:
				nameOfFile = nameOfFile + word
		if self.isYearRange:
			nameOfFile = nameOfFile + str(self.lowYear) + "." + str(self.highYear)
		nameOfFile = nameOfFile + ".csv"
		return nameOfFile

	# Good time to parse errors in formatting too
	def establishStrictness(self):
		if self.strictYearRange in ["ya", "True", "true", "yes", "absolutely"]:
			self.strictYearRange = True
		else:
			self.strictYearRange = False

	def checkIfHitDateinQueryRange(self, dateToCheck):
		yearList = dateToCheck.split("-")
		lower = int(yearList[0])
		higher = int(yearList[1])
		if lower < self.lowYear and higher > self.highYear:
			return True
		else:
			return False

	# What if list of papers?
	def parseNewspaperDictionary(self):
		dicParser = DictionaryMaker(self.newspaper, [self.lowYear, self.highYear], self.strictYearRange)
		self.newspaperDictionary = dicParser.getDictionary()

	def establishYearRange(self, yearRange):
		if len(yearRange) == 2:
			self.lowYear = int(yearRange[0])
			self.highYear = int(yearRange[1])
			self.isYearRange = True
		else:
			self.isYearRange = False

	def buildQuery(self):
		if self.isYearRange:
			if self.newspaper[0] == "noDict":
				self.baseQuery = '(dc.date >= "{firstYear}" and dc.date <= "{secondYear}") and (gallica adj "{' \
								 '{searchWord}}") sortby dc.date/sort.ascending '
			else:
				self.baseQuery = '(dc.date >= "{firstYear}" and dc.date <= "{secondYear}") and ((arkPress all "{{{{' \
								 'newsKey}}}}") and (gallica adj "{{searchWord}}")) sortby dc.date/sort.ascending '
			self.baseQuery = self.baseQuery.format(firstYear=str(self.lowYear), secondYear=str(self.highYear))
		else:
			if self.newspaper[0] == "noDict":
				self.baseQuery = '(gallica adj "{searchWord}") and (dc.type all "fascicule") sortby dc.date/sort.ascending'
			else:
				self.baseQuery = 'arkPress all "{{newsKey}}" and (gallica adj "{searchWord}") sortby dc.date/sort.ascending'
		self.baseQuery = self.baseQuery.format(searchWord=self.searchTerm)

	def runSearch(self):
		pass

	def findTotalResults(self):
		pass

	def updateDictionaries(self):
		self.newspaperDictionary.clear()
		for i in range(10):
			self.topTenPapers.append(["",0])
		for nameCountCode in self.paperNameCounts:
			paperName = nameCountCode[0]
			paperCount = nameCountCode[1]
			paperCode = nameCountCode[2]
			self.updateTopTenPapers(paperName, paperCount)
			self.newspaperDictionary.update({paperName : paperCode})
			self.numResultsForEachPaper.update({paperName : paperCount})
			#A little weird to calculate total results here
			self.sumUpTotalResults(paperCount)

	def updateTopTenPapers(self, name, count):
		for i in range(10):
			currentIndexCount = self.topTenPapers[i][1]
			if count > currentIndexCount:
				self.topTenPapers.insert(i, [name, count])
				del(self.topTenPapers[10:])
				break

	def generateTopTenPapers(self):
		dictionaryFile = "{0}-{1}".format("TopPaperDict", self.fileName)
		with open(os.path.join("../CSVdata", dictionaryFile), "w", encoding="utf8") as outFile:
			writer = csv.writer(outFile)
			for newspaper in self.topTenPapers:
				print(newspaper)
				newspaper[0] = newspaper[0].replace('"','')
				writer.writerow(newspaper)

	def sumUpTotalResults(self, toAdd):
		self.totalResults = self.totalResults + toAdd

	def makeChunkedDictionary(self, chunkSize):
		listOfSubDicts = []
		initialList = []
		for paper in self.newspaperDictionary:
			initialList.append(paper)
		currentIndex = 0
		for i in range(ceil((len(self.newspaperDictionary) / chunkSize)) - 1):
			subDict = {}
			subList = initialList[currentIndex:currentIndex+chunkSize]
			currentIndex = currentIndex + chunkSize
			for paper in subList:
				subDict[paper] = self.newspaperDictionary[paper]
			listOfSubDicts.append(subDict)
		subDict = {}
		subList = initialList[currentIndex:]
		for paper in subList:
			subDict[paper] = self.newspaperDictionary[paper]
		listOfSubDicts.append(subDict)
		self.chunkedNewspaperDictionary = listOfSubDicts

	def updateProgressPercent(self,iteration, total):
		self.progressPercent = int((iteration / total) * 100)
		print(self.progressPercent)

	def resetProgressIterations(self):
		self.progressIterations = 0





class FullSearchWithinDictionary(GallicaSearch):
	def __init__(self, searchTerm, newspaper, yearRange, strictYearRange):
		super().__init__(searchTerm, newspaper, yearRange, strictYearRange)

	def runSearch(self):
		self.resetProgressIterations()
		self.createWorkersForSearch()

	def createWorkersForSearch(self):
		progress = 0
		with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
			for result in executor.map(self.sendWorkersToSearch, self.chunkedNewspaperDictionary):
				paperName = result[0]
				resultList = result[1]
				numberResultsForEntirePaper = result[2]
				self.collectedQueries.extend(resultList)
				progress = progress + numberResultsForEntirePaper
				self.updateProgressPercent(progress, self.totalResults)
				self.numResultsForEachPaper.update({paperName: numberResultsForEntirePaper})

	def sendWorkersToSearch(self, newspaper):
		numberResultsInPaper = self.numResultsForEachPaper[newspaper]
		newspaperCode = self.newspaperDictionary[newspaper]
		newspaperQuery = self.baseQuery.format(newsKey=newspaperCode)
		newspaperHuntOverseer = UnlimitedOverseerOfNewspaperHunt(newspaperQuery, numberResultsInPaper)
		newspaperHuntOverseer.scourPaper()
		return [newspaper, newspaperHuntOverseer.getResultList(), newspaperHuntOverseer.getNumValidResults()]

	def findTotalResults(self):
		self.createWorkersForFindingTotalResults()

	def createWorkersForFindingTotalResults(self):
		chunkSize = 30
		self.makeChunkedDictionary(chunkSize)
		try:
			with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
				for i, result in enumerate(executor.map(self.findNumberResults, self.newspaperDictionary), 1):
					self.paperNameCounts = self.paperNameCounts + result
					self.updateProgressPercent(i, len(self.newspaperDictionary))
			self.updateDictionaries()
		except Exception as error:
			print(error)
			raise

	def findNumberResults(self, newspaper):
		session = GallicaSearch.makeSession()
		paperCounts = []
		newspaperCode = self.newspaperDictionary[newspaper]
		newspaperQuery = self.baseQuery.format(newsKey=newspaperCode)
		hunterForTotalNumberOfQueryResults = GallicaHunter(newspaperQuery, 1, 1, session)
		numberResultsForNewspaper = hunterForTotalNumberOfQueryResults.establishTotalHits(newspaperQuery, False)
		if numberResultsForNewspaper != 0:
			paperCounts.append([newspaper, numberResultsForNewspaper, newspaperCode])
		return paperCounts



class FullSearchNoDictionary(GallicaSearch):
	def __init__(self, searchTerm, newspaper, yearRange, strictYearRange):
		super().__init__(searchTerm, newspaper, yearRange, strictYearRange)

	def runSearch(self):
		iterations = ceil(self.totalResults / 50)
		startRecordList = []
		for i in range(iterations):
			startRecordList.append((i * 50) + 1)
		with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
			for i, result in enumerate(executor.map(self.sendWorkersToSearch, startRecordList), 1):
				self.updateProgressPercent(i, iterations)
				self.collectedQueries.extend(result)


	def sendWorkersToSearch(self, startRecord):
		batchHunter = self.sendQuery(self.baseQuery, startRecord=startRecord, numRecords=50)
		results = batchHunter.getResultList()
		return results

	def findTotalResults(self):
		hunterForTotalNumberOfQueryResults = GallicaSearch.sendQuery(self.baseQuery, numRecords=1, startRecord =1)
		self.totalResults = hunterForTotalNumberOfQueryResults.establishTotalHits(self.baseQuery, False)

	# make list of newspapers with number results. Do at the end of all queries (since # results updated during lower level runs)



