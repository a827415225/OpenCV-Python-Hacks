#!/usr/bin/env python

'''
optical_flow.py - Optical-flow velocity calculation and display using OpenCV

    To test:

      % optical_flow               # video from webcam
      % optical_flow -f FILENAME   # video from file
      % optical_flow -c CAMERA     # specific camera number
      % optical_flow -s N          # scale-down factor for flow image
      % optical_flow -m M          # move step in pixels

    Adapted from 
 
    https://code.ros.org/trac/opencv/browser/trunk/opencv/samples/python/fback.py?rev=2271

    Copyright (C) 2014 Simon D. Levy

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as 
    published by the Free Software Foundation, either version 3 of the 
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
'''

import cv
import time
import math
import optparse

class OpticalFlowCalculator:
    '''
    A class for optical flow calculations using OpenCV
    '''
    
    def __init__(self, frame_width, frame_height, scaledown=1,
                 perspective_angle=0, move_step=16, window_name=None, flow_color_rgb=(0,255,0)):
        '''
        Creates an OpticalFlow object for images with specified width and height.

        Optional inputs are:

          perspective_angle - perspective angle of camera, for reporting flow in meters per second
          move_step           - step size in pixels for sampling the flow image
          window_name       - window name for display
          flow_color_rgb    - color for displaying flow
        '''

        self.move_step = move_step
        self.mv_color_bgr = (flow_color_rgb[2], flow_color_rgb[1], flow_color_rgb[0])

        self.perspective_angle = perspective_angle

        self.window_name = window_name
        
        if window_name:
            cv.NamedWindow(window_name, 1 )

        size = (frame_width, frame_height)

        self.bgrbytes = bytearray(frame_width*frame_height * 3)
        self.image = cv.CreateImage(size, cv.IPL_DEPTH_8U, 3)

        frame_width  = int(frame_width/scaledown)
        frame_height = int(frame_height/scaledown)

        size = (frame_width, frame_height)
        self.frame2 = cv.CreateImage(size, cv.IPL_DEPTH_8U, 3)

        self.gray = cv.CreateImage(size, 8, 1)
        self.flow = cv.CreateImage(size, 32, 2)
        self.prev_gray = cv.CreateImage(size, 8, 1)

        self.frame_width = frame_width

        self.prev_time = None

    def processBytes(self, rgb_bytes, distance=None, timestep=1):
        '''
        Processes one frame of RGB bytes, returning summed X,Y flow.

        Optional inputs are:

          distance - distance in meters to image (focal length) for returning flow in meters per second
          timestep - time step in seconds for returning flow in meters per second
         '''

        self.bgrbytes[0::3] = rgb_bytes[2::3]
        self.bgrbytes[1::3] = rgb_bytes[1::3]
        self.bgrbytes[2::3] = rgb_bytes[0::3]
                        
        cv.SetData(self.image, self.bgrbytes, self.frame_width*3)
        
        return self.processFrame(self.image, distance, timestep)

    def processFrame(self, frame, distance=None, timestep=1):
        '''
        Processes one image frame, returning summed X,Y flow

        Optional inputs are:

          distance - distance in meters to image (focal length) for returning flow in meters per second
          timestep - time step in seconds for returning flow in meters per second
        '''

        cv.Resize(frame, self.frame2)

        cv.CvtColor(self.frame2, self.gray, cv.CV_BGR2GRAY)

        cv.CalcOpticalFlowFarneback(self.prev_gray, self.gray, self.flow)

        xsum, ysum = 0,0
        
        for y in range(0, self.flow.height, self.move_step):

            for x in range(0, self.flow.width, self.move_step):

                fx, fy = self.flow[y, x]
                xsum += fx
                ysum += fy

                cv.Line(self.frame2, (x,y), (int(x+fx),int(y+fy)), self.mv_color_bgr)
                cv.Circle(self.frame2, (x,y), 1, self.mv_color_bgr, -1)

        if self.window_name:
            cv.ShowImage(self.window_name, self.frame2)
            if cv.WaitKey(1) & 0x000000FF== 27: # ESC
                return None

        self.prev_gray, self.gray = self.gray, self.prev_gray        
        
        # Default to system time if no timestep
        curr_time = time.time()
        if not timestep:
            timestep = (curr_time - self.prev_time) if self.prev_time else 1
        self.prev_time = curr_time

       # Normalize and divide by timestep
        return  self._get_velocity(xsum, self.flow.width,  distance, timestep), \
                self._get_velocity(ysum, self.flow.height, distance, timestep)

    def _get_velocity(self, sum_velocity_pixels, dimsize_pixels, distance_meters, timestep_seconds):

        count =  (self.flow.height * self.flow.width) / self.move_step**2

        average_velocity_pixels_per_second = sum_velocity_pixels / count / timestep_seconds

        return self._velocity_meters_per_second(average_velocity_pixels_per_second, dimsize_pixels, distance_meters) \
               if self.perspective_angle and distance_meters \
               else average_velocity_pixels_per_second

    def _velocity_meters_per_second(self, velocity_pixels_per_second, dimsize_pixels, distance_meters):

        distance_pixels = (dimsize_pixels/2) / math.tan(self.perspective_angle/2)         

        pixels_per_meter = distance_pixels / distance_meters
         
        return velocity_pixels_per_second / pixels_per_meter

if __name__=="__main__":

    parser = optparse.OptionParser()

    parser.add_option("-f", "--file",  dest="filename", help="Read from video file", metavar="FILE")
    parser.add_option("-s", "--scaledown", dest="scaledown", help="Fractional image scaling", metavar="SCALEDOWN")
    parser.add_option("-c", "--camera", dest="camera", help="Camera number", metavar="CAMERA")
    parser.add_option("-m", "--movestep", dest="movestep", help="Move step (pixels)", metavar="MOVESTEP")

    (options, _) = parser.parse_args()

    camno = int(options.camera) if options.camera else 0

    capture = cv.CaptureFromCAM(camno) if not options.filename else cv.CaptureFromFile(options.filename)

    width   = int(cv.GetCaptureProperty(capture, cv.CV_CAP_PROP_FRAME_WIDTH))
    height  = int(cv.GetCaptureProperty(capture, cv.CV_CAP_PROP_FRAME_HEIGHT))

    scaledown = int(options.scaledown) if options.scaledown else 1

    movestep = int(options.movestep) if options.movestep else 16

    flow = OpticalFlowCalculator(width, height, window_name='Optical Flow', scaledown=scaledown, move_step=movestep) 
    start_sec = time.time()
    count = 0

    while True:

        frame = cv.QueryFrame(capture)

        count += 1
            
        if not frame:
            break

        result = flow.processFrame(frame)

        if not result:
            break

    elapsed_sec = time.time() - start_sec

    print('%dx%d image: %d frames in %3.3f sec = %3.3f frames / sec' % 
             (flow.frame2.width, flow.frame2.height, count, elapsed_sec, count/elapsed_sec))
