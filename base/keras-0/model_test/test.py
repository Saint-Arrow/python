#https://github.com/keras-team/keras-io/blob/master/examples/vision/image_classification_from_scratch.py


import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import os


path = os.path.dirname(__file__)
os.chdir(path)

image_size = (180, 180)
batch_size = 32

model=keras.models.load_model("save_at_12.h5");


img = keras.preprocessing.image.load_img(
    "6790.jpg", target_size=image_size
)


img_array = keras.preprocessing.image.img_to_array(img)
img_array = tf.expand_dims(img_array, 0)  # Create batch axis

predictions = model.predict(img_array)
score = predictions[0]
print(
    "This image is %.2f percent cat and %.2f percent dog."
    % (100 * (1 - score), 100 * score)
)


img = keras.preprocessing.image.load_img(
    "10837.jpg", target_size=image_size
)
img_array = keras.preprocessing.image.img_to_array(img)
img_array = tf.expand_dims(img_array, 0)  # Create batch axis

predictions = model.predict(img_array)
score = predictions[0]
print(
    "This image2 is %.2f percent cat and %.2f percent dog."
    % (100 * (1 - score), 100 * score)
)




