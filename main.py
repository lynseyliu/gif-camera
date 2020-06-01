from imutils import face_utils
from picamera.array import PiRGBArray
from picamera import PiCamera
from PIL import Image, ImageDraw, ImageFont
from waveshare_2inch_LCD import ST7789
import cv2 as cv
import dlib
import imutils
import io
import json
import numpy as np
import os
import pytumblr
import requests
import RPi.GPIO as GPIO
import time
import uuid

# show startup screen
print('starting up...')

'''
Initialize face and filters
'''
# init face detector and create predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor('shape_predictor_68_face_landmarks.dat')

# init filters


'''
Utils
'''
# convert dlib box to (x, y, w, h)
def rect_to_bb(rect):
    x = rect.left()
    y = rect.top()
    w = rect.right() - x
    h = rect.bottom() - y
    return (x, y, w, h)

# convert landmarks to (x, y) tuples
def shape_to_np(shape, dtype="int"):
    coords = np.zeros((68, 2), dtype=dtype)
    for i in range(0, 68):
    	coords[i] = (shape.part(i).x, shape.part(i).y)
    return coords

# get face landmarks from frame
def detect_face_landmarks(frame):
    # convert to grayscale cv image
    cv_image = np.array(frame)
    cv_image = cv_image[:, :, ::-1].copy() # convert RGB to BGR
    frame_gray = cv.cvtColor(cv_image, cv.COLOR_BGR2GRAY)
   
    # detect faces in the grayscale frame
    rects = detector(frame_gray, 0)

    faces = []
    # loop over the face detections
    for rect in rects:
    	# determine the facial landmarks for the face region, then
    	# convert the facial landmark (x, y)-coordinates to a NumPy
    	# array
    	shape = predictor(frame_gray, rect)
    	shape = face_utils.shape_to_np(shape)
        faces.append(shape)

        '''
    	# loop over the (x, y)-coordinates for the facial landmarks
    	# and draw them on the image
    	for (x, y) in shape:
            cv.circle(cv_image, (x, y), 1, (0, 0, 255), -1)
        '''
    return faces
    #pil_image = Image.fromarray(cv.cvtColor(cv_image, cv.COLOR_BGR2RGB))
    #return pil_image

def draw_current_filter(frame):
    faces = detect_face_landmarks(frame)
    return frame

def get_filepath(extension):
    capture_folder = 'capture'
    image_name = str(uuid.uuid4())
    filepath = os.path.join(capture_folder, image_name + extension)
    return filepath

'''
Initialize hardware
'''
# init display
disp = ST7789.ST7789()
disp.Init()
disp.clear()

# init camera TODO: rename to viewfinder, init another camera for capture that grabs higher res?
camera = PiCamera()
camera.resolution = (disp.height * 2, disp.width * 2)
camera.framerate = 32
time.sleep(0.1) # allow camera to warm up :)

# GPIO settings
buttons = (26, 16, 12)
GPIO.setup(buttons, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(26, GPIO.RISING)
GPIO.add_event_detect(16, GPIO.RISING)
GPIO.add_event_detect(12, GPIO.RISING)
buttons_init = False

'''
Initialize Tumblr
'''
# set up pytumblr client
with open('tumblr_secrets.json') as f:
    secrets = json.load(f)

client = pytumblr.TumblrRestClient(
    secrets['consumer_key'],
    secrets['consumer_secret'],
    secrets['token'],
    secrets['token_secret']
)
tumblr_username = 'pi-cam'

'''
Capture
'''
print('begin capture')
stream = io.BytesIO()
gif_frames = []

for frame in camera.capture_continuous(stream, format='jpeg', use_video_port=True):
    stream.seek(0)
    
    image = Image.open(stream)
    draw_current_filter(image)
    disp_image = image.resize((disp.height, disp.width), Image.NEAREST)
    disp.ShowImage(disp_image)
    
    stream.seek(0)
    stream.truncate()

    # small delay between gif frames
    if len(gif_frames) != 0:
        time.sleep(1)

    # process gif on third frame
    if len(gif_frames) == 2:
        # save frames
        filepath = get_filepath('.gif')

        # upload gif and reset
        client.create_photo(tumblr_username, state="published", tags=["GIF"], data=filepath)
        gif_frames = []

    if buttons_init:
        # image capture button
        if GPIO.event_detected(12):
            # show capturing screen
            print('capturing image...')
           
            # save frame
            filepath = get_filepath('.jpg')
            image.save(filepath, format='JPEG')

            # upload photo
            client.create_photo(tumblr_username, state="published", tags=[], data=filepath)

        # gif capture button
        if GPIO.event_detected(16):
            # show capturing screen
            print('capturing gif...')

            gif_frames.append(image)
        
        # filter toggle
        if GPIO.event_detected(26):
            print('toggle filter')

    buttons_init = True
 
