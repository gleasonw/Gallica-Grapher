import csv
import rpy2.robjects as robjects
import shutil
import os

from rpy2.robjects.lib.ggplot2 import (ggplot, aes,labs,geom_bar)
from rpy2.robjects.packages import importr



class GallicaPackager:
    def __init__(self, csvFile, tenMostPapers):
        self.fileName = csvFile
        self.graphFileName = ''
        self.tenMostPapers = []
        self.establishTopPapers(tenMostPapers)


    def establishTopPapers(self, tenMostPapers):
        if tenMostPapers is None:
            dictionaryFile = "{0}-{1}".format("TopPaperDict", self.fileName)
            with open(os.path.join("./CSVdata", dictionaryFile)) as inFile:
                reader = csv.reader(inFile)
                for newspaper in reader:
                    self.tenMostPapers.append(newspaper)
        else:
            self.tenMostPapers = tenMostPapers

    def makeGraph(self):
        self.makeGraphFileName()

        grdevices = importr('grDevices')
        zoo = importr('zoo')
        base = importr('base')
        utils = importr('utils')
        dplyr = importr('dplyr')
        stringr = importr('stringr')
        scales = importr('scales')
        lubridate = importr('lubridate')
        tibble = importr('tibble')

        nameOcc = utils.read_csv(os.path.join("./CSVdata", self.fileName), encoding="UTF-8", stringsAsFactors=False, header=True)
        nameOcc = self.readyColumnsForGraphing(nameOcc)
        print(nameOcc)

        robjects.r('''
        createGraph <- function(dataToGraph, title){
            graphOfHits <- ggplot(dataToGraph, aes(x=yearmon, y=total, fill=fillPaper)) +\
                geom_col() + \
                scale_x_yearmon(breaks=date_breaks("months")) + \
                labs(title=title, x="Year/month", y="occurrence count") +\
                theme(axis.text = element_text(size=12), axis.text.x = element_text(angle = 45, hjust = 1))
            plot(graphOfHits)
        }
        ''')
        titleSplit = self.fileName.split("--")
        searchTermProbably = titleSplit[0]
        graphTitle = "{0} usage by year/mon".format(searchTermProbably)

        grdevices.png(file=self.graphFileName, width=1920, height=1080)
        dataGrapher = robjects.globalenv['createGraph']
        dataGrapher(nameOcc, graphTitle)
        grdevices.dev_off()
        shutil.move(os.path.join("./", self.graphFileName), os.path.join("./Graphs", self.graphFileName))


    def readyColumnsForGraphing(self, csvResults):
        robjects.r('''
            nameOccMutateForFill <- function(csvResults, topTenPapers){ 
                paperVector <- unlist(topTenPapers,recursive=TRUE)
                csvResults <- csvResults %>% mutate(date=as.yearmon(date))
                csvResults <- csvResults %>% mutate(fillPaper=ifelse(csvResults$journal %in% paperVector, csvResults$journal, 'Other')) 
                yearMonthCounts <- tibble(yearmon=csvResults$date,fillPaper=csvResults$fillPaper,count=1)\
                                %>% group_by(yearmon, fillPaper)\
                                %>% summarise(total = sum(count))
                return(yearMonthCounts)
                }
            ''')
        mutateFunction = robjects.globalenv['nameOccMutateForFill']
        return mutateFunction(csvResults, self.tenMostPapers)


    def makeGraphFileName(self):
        self.graphFileName = self.fileName[0:len(self.fileName)-4]
        self.graphFileName = self.graphFileName + ".png"
