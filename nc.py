from __future__ import division

import sqlite3
import math
import re

import tablib

from nltk.stem.lancaster import LancasterStemmer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk import FreqDist
from nltk import pos_tag


#DB init
conn = sqlite3.connect('db.db')
c = conn.cursor()

#preprocess
def preprocess(content):
	stopset = set(stopwords.words('english'))
	#replace punctuation and tag with space
	tokens = word_tokenize(re.sub(r'<p>|</p>|[^A-Za-z ]', ' ', content.lower())) 
	pos_list = pos_tag(tokens)
	s_tokens = list()

	#noun and verb only
	for pos in pos_list:
		#print pos[1]
		if pos[1] in ['NN', 'NNS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ']:
			s_tokens.append(pos[0])

	wordfreq = FreqDist(s_tokens)
	stemfreq = dict()
	st = LancasterStemmer()
	for word, freq in wordfreq.items():
		#stopwords
		if word in stopset:
			del wordfreq[word]
			continue
		#tiny words
		if len(word) <= 2:
			del wordfreq[word]
			continue
		#stemmer
		stem = st.stem(word)
		try:
			stemfreq[stem]+=freq
		except:
			stemfreq[stem]=freq
	return stemfreq

#class def

#article
class Article:
	def __init__(self, _id, title, source, category, content, genre):
		self._id = _id
		self.title = title
		self.source = source
		self.category = category
		self.content = content
		self.genre = genre #0=training 1=testing
		self.wordfreq = dict()
		self.freqsum = 0
		self.wf_table = 'wordfreq_training' if (genre==0) else 'wordfreq_testing'

	def createWordFreq(self):
		#preprocess
		self.wordfreq = preprocess(self.content)

	def commitWordFreq(self):
		for word, freq in self.wordfreq.items():
			c.execute('INSERT INTO '+self.wf_table+' VALUES (NULL,?,?,?)', (word, freq, self._id))

	def getWordFreq(self):
		for row in c.execute('SELECT word, freq FROM '+self.wf_table+' WHERE of=?', (self._id,)):
			self.wordfreq[row[0]]=row[1]
			self.freqsum += row[1]


#category
class Category:
	def __init__(self, name):
		self.name = name
		self.wordfreq = dict()
		self.freqsum = 0

	def appendArticle(self, article):
		for word, freq in article.wordfreq.items():
			try:
				self.wordfreq[word]+=freq
			except:
				self.wordfreq[word]=freq
			self.freqsum+=freq

	def commitCategory(self):
		for word, freq in self.wordfreq.items():
			c.execute('INSERT INTO wordfreq_category VALUES (NULL, ?, ?, ?)', (word, freq, self.name))

	def getWordFreq(self):
		for row in c.execute('SELECT word, freq FROM wordfreq_category WHERE of=?', (self.name,)):
			self.wordfreq[row[0]]=row[1]
			self.freqsum += row[1]




#Calculator
class Calculator:
	def __init__(self):
		self.e_dist = dict()

	def calEDistance(self, article, category):
		attr = list(list(category.wordfreq.keys()) + list(article.wordfreq.keys()))
		outcome = 0
		for word in attr:
			try:
				category.wordfreq[word]
			except:
				category.wordfreq[word]=0

			try:
				article.wordfreq[word]
			except:
				article.wordfreq[word]=0

			try:
				outcome += math.pow(category.wordfreq[word]/category.freqsum - article.wordfreq[word]/article.freqsum, 2)
			except:
				continue
			#print word#+' '+str(category.wordfreq[word])+' '+str(article.wordfreq[word])

		outcome = math.sqrt(outcome)
		
		try:
			self.e_dist[article._id][category.name] = outcome
		except:
			self.e_dist[article._id] = dict()
			self.e_dist[article._id][category.name] = outcome
		return outcome

	def commitEDistance(self):
		for article in self.e_dist.keys():
			for category, freq in self.e_dist[article].items():
				c.execute('INSERT INTO e_distance VALUES (NULL, ?,?,?)', (article, freq, category))

	def getEDistance(self):
		for row in c.execute('SELECT testing_id, distance, of FROM e_distance'):
			try:
				self.e_dist[row[0]][row[2]]=row[1]
			except:
				self.e_dist[row[0]]=dict()
				self.e_dist[row[0]][row[2]]=row[1]

	def exportEDdistance(self, ta):
		data = [[0]*10 for i in range(len(self.e_dist.keys())+1)]
		row = dict()
		col = dict()
		data[0][0]='Title'
		data[0][1]='Original Category/e_dist'
		data[0][9]='Outcome'
		for article in self.e_dist.keys():
			#indexing
			try:
				row[article]
			except:
				row[article]=len(row)
		for category in self.e_dist[1].keys():
			try:
				col[category]
			except:
				col[category]=len(col)
			data[0][col[category]+2]=category #training category

		for article in self.e_dist.keys():
			for category, freq in self.e_dist[article].items():
				x = col[category]+2 #offset 2
				y = row[article]+1 #offset 1
				if (data[y][0]==0):
					data[y][0] = ta[article].title
					data[y][1] = ta[article].category #original category
				data[y][x] = freq

		for y in range(1, len(data)):
			least=1
			outcome=''
			for x in range(2, 8):
				if(data[y][x]<least):
					least=data[y][x]
					outcome=data[0][x]
			data[y][9]=outcome



		data = tablib.Dataset(*data)
		#write
		f = open("e_dist.csv", "w+")
		f.write(data.csv)
		f.close()




def initTrainingArticle(start=0, end=400):
	#for row in c.execute('SELECT * FROM article_cnn WHERE id >= 8'):
	c.execute('SELECT * FROM article_cnn WHERE id BETWEEN ? AND ?',(start, end))
	rows = c.fetchall()
	for row in rows:
		print row[1]
		a = Article(_id=row[0], title=row[1], source=row[2], category=row[6], content=row[7], genre=0)
		a.createWordFreq()
		a.commitWordFreq()
		#print a.wordfreq
		a = ''

def initTestingArticle(start=0, end=100):
	#for row in c.execute('SELECT * FROM article_cnn WHERE id >= 8'):
	c.execute('SELECT * FROM article_fox WHERE id BETWEEN ? AND ?',(start, end))
	rows = c.fetchall()
	for row in rows:
		print row[1]
		a = Article(_id=row[0], title=row[1], source=row[2], category=row[6], content=row[7], genre=1)
		a.createWordFreq()
		a.commitWordFreq()
		#print a.wordfreq
		a = ''
	
def initCategory():
	c.execute('SELECT name FROM category')
	rs = c.fetchall()
	for r in rs:
		category_name = r[0]
		c.execute('SELECT * FROM article_cnn WHERE category = ?',(category_name,))
		rows = c.fetchall()
		cate = Category(name=category_name)
		for row in rows:
			print row[1]
			print row[6]
			a = Article(_id=row[0], title=row[1], source=row[2], category=row[6], content=row[7], genre=0)
			a.getWordFreq()
			cate.appendArticle(a)
		cate.commitCategory()

def retrieveCategory():
	c.execute('SELECT name FROM category')
	rows = c.fetchall()
	cates = list()
	for row in rows:
		cate = Category(name=row[0])
		cate.getWordFreq()
		cates.append(cate)
	return cates

def retrieveTestingArticle():
	ta = dict()
	for row in c.execute('SELECT * FROM article_fox'):
		ta[row[0]] = Article(_id=row[0], title=row[1], source=row[2], category=row[6], content=row[7], genre=1)
	return ta


def initDistance():
	cal = Calculator()
	cates = retrieveCategory()
	c.execute('SELECT * FROM article_fox')
	rows = c.fetchall()
	for row in rows:
		a = Article(_id=row[0], title=row[1], source=row[2], category=row[6], content=row[7], genre=1)
		a.getWordFreq()
		cate_dist = list()
		for cate in cates:
			cate_dist.append(cal.calEDistance(a, cate))
		#print cal.e_dist
		cal.commitEDistance()
		print a.title+'\n'+str(cate_dist)

def initExportEDistance():
	cal = Calculator()
	cal.getEDistance()
	cal.exportEDdistance(retrieveTestingArticle())

def eraseRecords():
	c.execute('DELETE FROM e_distance') #erase Table
	c.execute('DELETE FROM wordfreq_category') #erase Table
	c.execute('DELETE FROM wordfreq_testing') #erase Table
	c.execute('DELETE FROM wordfreq_training') #erase Table
	c.execute('VACUUM')
	conn.commit()

def deployPreprocess():
	eraseRecords()
	initTrainingArticle()
	initTestingArticle()
	initCategory()
	initDistance()


deployPreprocess()

conn.commit()
conn.close()
print('YEAH!')