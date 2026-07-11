import numpy as np

# Define resolutions
input_width = 1920
input_height = 1080
output_width = 720
output_height = 480

# Read UYVY file
with open('output.uyvy', 'rb') as f:
    uyvy_data = np.fromfile(f, dtype=np.uint8)

# Reshape data for UYVY format (each pixel is represented by 2 bytes)
uyvy = uyvy_data.reshape((input_height, input_width * 2))

# Create output array
output_uyvy = np.zeros((output_height, output_width * 2), dtype=np.uint8)

# Calculate cropping area (centered crop)
x_start = (input_width - output_width) // 2
y_start = (input_height - output_height) // 2

# Perform cropping
for h in range(output_height):
    for w in range(0, output_width * 2, 4):
        # Copy UYVY values
        output_uyvy[h, w] = uyvy[y_start + h, x_start * 2 + w]
        output_uyvy[h, w+1] = uyvy[y_start + h, x_start * 2 + w+1]
        output_uyvy[h, w+2] = uyvy[y_start + h, x_start * 2 + w+2]
        output_uyvy[h, w+3] = uyvy[y_start + h, x_start * 2 + w+3]

# Save cropped UYVY file
with open('output_cropped.uyvy', 'wb') as f:
    output_uyvy.tofile(f)

print("Cropping completed successfully!")