# The MIT License (MIT)
# 
# Copyright (c) 2015 Ryan Gibson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from PIL import Image
import math, os, struct, timeit

# These paths are to be changed by the user
input_image_path = "input_image.png"
steg_image_path = "steg_image.png"
input_file_path = "input.zip"
output_file_path = "output.zip"

buffer = 0
buffer_length = 0

# Number of least significant bits containing/to contain data in image
num_lsb = 2

def prepare_hide():
    # Prepare files for reading and writing for hiding data.
    global image, input_file
    
    try:
        image = Image.open(input_image_path)
        input_file = open(input_file_path, "rb")
    except FileNotFoundError:
        print("Input image or file not found, will not be able to hide data.")
        
def prepare_recover():
    # Prepare files for reading and writing for recovering data.
    global steg_image, output_file
    
    try:
        steg_image = Image.open(steg_image_path)
        output_file = open(output_file_path, "wb+")
    except FileNotFoundError:
        print("Steganographed image not found, will not be able to recover data.")

def reset_buffer():
    global buffer, buffer_length
    
    buffer = 0
    buffer_length = 0

def and_mask(index, n):
    # Returns an int used to set n bits to 0 from the index:th bit when using
    # bitwise AND on a integer of 8 bits or less.
    # Ex: and_mask(3,2) --> 0b11100111 = 231.
    return 255 - ((1 << n) - 1 << index)

def get_filesize(path):
    # Returns the filesize in bytes of the file at path
    return os.stat(path).st_size

def max_bits_to_hide():
    # Returns the number of bits we're able to hide in the image
    # using num_lsb least significant bits.
    # 3 color channels per pixel, num_lsb bits per color channel.
    try:
        return int(3 * image.size[0] * image.size[1] * num_lsb)
    except NameError:
        return int(3 * steg_image.size[0] * steg_image.size[1] * num_lsb)

def bits_in_max_filesize():
    # Returns the number of bits needed to store the size of the file.
    return max_bits_to_hide().bit_length()

def read_byte_to_buffer():
    # Reads a byte from the input file and adds it to the buffer.
    # If the end of file has been reached, its length is set to -1.
    global buffer, buffer_length
    
    new_byte = input_file.read(1)
    if(new_byte != b''):
        buffer += int.from_bytes(new_byte, 'big') << buffer_length
        buffer_length += 8
    else:
        buffer = 0
        buffer_length = -1
        
def read_bits_from_buffer(n):
    # Removes the first n bits from the buffer and returns them.
    global buffer, buffer_length
    
    bits = buffer % (1 << n)
    buffer >>= n
    buffer_length -= n
    return bits 

def hide_data():
    # Hides the data from the input file in the input image.
    global buffer, buffer_length
    
    start = timeit.default_timer()
    prepare_hide()
    reset_buffer()
    
    # (x,y) is the position of the current pixel.
    x = 0
    y = 0

    # We add the size of the input file to the beginning of the buffer.
    buffer += get_filesize(input_file_path)
    buffer_length += bits_in_max_filesize()
    
    print("Hiding", buffer, "bytes")
    
    while (buffer_length != -1 and y < image.size[1]):
        rgb = list(image.getpixel((x, y)))
        for i in range(3):
            if(buffer_length < num_lsb):
                # If we need more data in the buffer, add a byte from the file to it.
                read_byte_to_buffer()
            if (buffer_length != -1):
                # Replace the num_lsb least significant bits of each color
                # channel with the first num_lsb bits from the buffer.
                rgb[i] &= and_mask(0, num_lsb)
                rgb[i] |= read_bits_from_buffer(num_lsb)
                
        image.putpixel((x, y), tuple(rgb))
            
        x += 1
        if (x >= image.size[0]):
            x = 0
            y += 1
    image.save(steg_image_path)
    stop = timeit.default_timer()
    print("Runtime: {0:.2f} s".format(stop - start))

def recover_data():
    # Writes the data from the steganographed image to the output file
    global buffer, buffer_length
    
    start = timeit.default_timer()
    prepare_recover()
    reset_buffer()
    
    x = 0
    y = 0
    
    pixels_used_for_filesize = math.ceil(bits_in_max_filesize() / (3 * num_lsb))
    for i in range(pixels_used_for_filesize):
        rgb = list(steg_image.getpixel((x, y)))
        for i in range(3):
            # Add the num_lsb least significant bits 
            # of each color channel to the buffer.
            buffer += (rgb[i] % (1 << num_lsb) << buffer_length)
            buffer_length += num_lsb
        
        x += 1
        if (x > steg_image.size[0]):
            x = 0
            y += 1
    
    # Get the size of the file we need to recover.
    bytes_to_recover = read_bits_from_buffer(bits_in_max_filesize())
    print("Looking to recover", bytes_to_recover, "bytes")

    while (bytes_to_recover > 0):        
        rgb = list(steg_image.getpixel((x, y)))
        for i in range(3):
            # Add the num_lsb least significant bits 
            # of each color channel to the buffer.
            buffer += (rgb[i] % (1 << num_lsb)) << buffer_length
            buffer_length += num_lsb
            
        x += 1
        if (x >= steg_image.size[0]):
            x = 0
            y += 1
        
        while (buffer_length >= 8 and bytes_to_recover > 0):
            # If we have more than a byte in the buffer, write it to the output file
            # and decrement the number of bytes left to recover.
            bits = read_bits_from_buffer(8)
            output_file.write(struct.pack('1B', bits))
            bytes_to_recover -= 1

    output_file.close()
    
    stop = timeit.default_timer()
    print("Runtime: {0:.2f} s".format(stop - start))
            
def analysis():
    # Find how much data we can hide and the size of the data to be hidden
    prepare_hide()
    print("Image resolution: (", image.size[0], ",", image.size[1], ")")
    print("Using", num_lsb, "LSBs, we can hide: \t", int(max_bits_to_hide() / 8), "B")
    print("Size of input file: \t\t", get_filesize(input_file_path), "B")
    print("Filesize tag: \t\t\t", math.ceil(bits_in_max_filesize() / 8), "B")