#读取bmp图片 lenna.bmp
#把每个像素的RGB数据转为8bit的YUV数据
#按照 UY VY UY VY 的规律存储每个像素点的数据到文件 lenna_512x512_uyvy.bin中

#等效命令
#ffmpeg -i lenna.bmp -vf "scale=512:512,format=uyvy422" -f rawvideo -video_size 512x512 lenna_512x512_uyvy.bin
#ffplay -f rawvideo -pix_fmt uyvy422 -video_size 512x512 -i lenna_512x512_uyvy.bin

import cv2
import numpy as np

def bmp_to_uyvy(input_path, output_path):
    """
    Read BMP image lenna.bmp, convert RGB to 8-bit YUV data,
    and store in UYVY format (UY VY UY VY pattern) in output file.
    """
    # Read the BMP image
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image from {input_path}")
    
    # Convert BGR (OpenCV default) to RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Convert RGB to YUV
    img_yuv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YUV)
    
    # Get image dimensions
    height, width, _ = img_yuv.shape
    
    # Create UYVY format array
    # UYVY format: U0 Y0 V0 Y1 U2 Y2 V2 Y3 ...
    uyvy_data = np.zeros((height, width * 2), dtype=np.uint8)
    
    for y in range(height):
        for x in range(width):
            # Extract Y, U, V values
            y_val = img_yuv[y, x, 0]  # Y component
            u_val = img_yuv[y, x, 1]  # U component
            v_val = img_yuv[y, x, 2]  # V component
            
            # For UYVY format, even pixels store UY, odd pixels store VY
            if x % 2 == 0:  # Even pixel
                uyvy_data[y, x * 2] = u_val      # U
                uyvy_data[y, x * 2 + 1] = y_val  # Y
            else:  # Odd pixel
                uyvy_data[y, x * 2 ] = v_val  # V (placed in previous position)
                uyvy_data[y, x * 2 +1] = y_val      # Y
    
    # Flatten the array to 1D
    uyvy_flat = uyvy_data.flatten()
    
    # Write to binary file
    with open(output_path, 'wb') as f:
        f.write(uyvy_flat.tobytes())

# Alternative, more efficient implementation using numpy operations
def bmp_to_uyvy_optimized(input_path, output_path):
    """
    Optimized version using numpy operations for faster processing
    """
    # Read the BMP image
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image from {input_path}")
    
    # Convert BGR to RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Convert RGB to YUV
    img_yuv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YUV)
    
    # Extract Y, U, V channels
    Y = img_yuv[:, :, 0].astype(np.uint8)  # Y channel
    U = img_yuv[:, :, 1].astype(np.uint8)  # U channel
    V = img_yuv[:, :, 2].astype(np.uint8)  # V channel
    
    # Create output array for UYVY format
    height, width = Y.shape
    uyvy_output = np.zeros((height, width * 2), dtype=np.uint8)
    
    # For UYVY, every two pixels form a group with 4 bytes: U0 Y0 V0 Y1
    uyvy_output[:, 0::4] = U[:, ::2]  # U values for even pixels
    uyvy_output[:, 1::2] = Y.flatten()  # All Y values
    uyvy_output[:, 2::4] = V[:, 1::2]  # V values for odd pixels
    
    # Flatten and write to binary file
    uyvy_flat = uyvy_output.flatten()
    with open(output_path, 'wb') as f:
        f.write(uyvy_flat.tobytes())

if __name__ == "__main__":
    # Process the image as per requirements
    bmp_to_uyvy("lenna.bmp", "lenna_512x512_uyvy.bin")
    print("Conversion completed: lenna.bmp -> lenna_512x512_uyvy.bin")
