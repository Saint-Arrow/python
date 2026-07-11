"""
https://blog.csdn.net/qq_42722197/article/details/120620542?ops_request_misc=&request_id=&biz_id=102&utm_term=keras%2010%E5%88%86%E9%92%9F&utm_medium=distribute.pc_search_result.none-task-blog-2~all~sobaiduweb~default-0-120620542.142^v24^pc_rank_34,157^v15^new_3&spm=1018.2226.3001.4187

"""
import numpy as np
np.random.seed(1337)

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from keras.layers import Dense, Activation

import os
path = os.path.dirname(__file__)
os.chdir(path)


import matplotlib.pyplot as plt
X=np.linspace(-1,1,200)
np.random.shuffle(X)
Y=1*X + 2 +np.random.normal(0,0.05,(200,))
#plt.scatter(X,Y)
#plt.show()

X_train,Y_train=X[:160],Y[:160]
X_test,Y_test=X[160:],Y[160:]

model= keras.Sequential()
model.add(Dense(1,input_shape=(1,)))
model.compile(loss="mse",optimizer="sgd")

print("start train...")
for step in range(301):
    cost=model.train_on_batch(X_train,Y_train)
    if step % 100 == 0:
        print("cost:",cost)

weight = model.layers[0].get_weights()
print(type(weight),weight)
Y_pred=model.predict(X_test)
plt.scatter(X_test,Y_test)
plt.plot(X_test,Y_pred)
plt.show()
