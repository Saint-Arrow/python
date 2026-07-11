class a():
	def pa(self):  #有self，就是对象方法，需要用对象来调用
		print ("a方法")
class b():
	def pa(self):
		print ("b方法")
class c(a,b):
	def class_method():
		print("class_method")
	def pp(self):
		#super(a,self).pa()
		a.pa(self)
		b.pa(self)
	
test=c()
c.class_method() #测试 class方法
test.pa()        #测试 广度优先
test.pp()        #测试 super的局限以及使用未绑定方式调用