"""
https://blog.csdn.net/qq_42722197/article/details/120620542?ops_request_misc=&request_id=&biz_id=102&utm_term=keras%2010%E5%88%86%E9%92%9F&utm_medium=distribute.pc_search_result.none-task-blog-2~all~sobaiduweb~default-0-120620542.142^v24^pc_rank_34,157^v15^new_3&spm=1018.2226.3001.4187

"""
import numpy as np
np.random.seed(1337)

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from keras.models import Model
from keras.layers import Dense, Activation

import os
path = os.path.dirname(__file__)
os.chdir(path)


import matplotlib.pyplot as plt
X=np.linspace(-1,1,200)
np.random.shuffle(X)
Y=2*X*X + 2
#Y=2*X*X + 2 +np.random.normal(0,0.05,(200,))
#plt.scatter(X,Y)
#plt.show()

X_train,Y_train=X[:150],Y[:150]
X_test,Y_test=X[150:],Y[150:]

model= keras.Sequential()
#units 代表
model.add(Dense(units=150,input_dim=1,activation="relu"))
model.add(Dense(150,activation="relu"))
model.add(Dense(1))


#model.compile(optimizer="adam",loss="mean_squared_error") 
model.compile(loss="mse",optimizer="sgd")

print("start train...")
cost=model.fit(X_train,Y_train,epochs=500)


weight = model.layers[0].get_weights()
print(type(weight),weight)
weight = model.layers[1].get_weights()
print(type(weight),weight)

model.summary()

Y_pred=model.predict(X_train)
print(X_train[0],Y_train[0],Y_pred[0])

#plt.plot(X_train,Y_train)
plt.scatter(X_train,Y_pred)
plt.show()



